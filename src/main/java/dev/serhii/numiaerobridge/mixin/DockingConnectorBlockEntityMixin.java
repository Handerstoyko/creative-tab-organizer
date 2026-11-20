package dev.serhii.numiaerobridge.mixin;

import com.simibubi.create.foundation.blockEntity.SmartBlockEntity;
import com.simibubi.create.foundation.blockEntity.behaviour.BlockEntityBehaviour;
import dev.serhii.numiaerobridge.DockingConnectorSalePointAccess;
import dev.serhii.numiaerobridge.DockingConnectorSalePointBehaviour;
import dev.serhii.numiaerobridge.NumismaticsAeronauticsBridge;
import net.minecraft.core.HolderLookup;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.world.item.ItemStack;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

import java.lang.reflect.InvocationHandler;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.util.List;

/**
 * Adds a buffered Numismatics interface to both resource channels of a Docking Connector.
 * A connector is configured for either items or fluids before binding a SalePoint.
 */
@Mixin(
    targets = "dev.simulated_team.simulated.content.blocks.docking_connector.DockingConnectorBlockEntity",
    remap = false
)
public abstract class DockingConnectorBlockEntityMixin implements DockingConnectorSalePointAccess {
    private static final String ABSTRACT_CONTAINER =
        "dev.simulated_team.simulated.multiloader.inventory.AbstractContainer";
    private static final String ITEM_INFO_WRAPPER =
        "dev.simulated_team.simulated.multiloader.inventory.ItemInfoWrapper";

    @Unique
    private boolean numiaerobridge$fluidMode;

    @Unique
    private DockingConnectorSalePointBehaviour numiaerobridge$salePointBehaviour;

    @Inject(method = "addBehaviours", at = @At("TAIL"), remap = false)
    private void numiaerobridge$addSalePointBehaviour(
        List<BlockEntityBehaviour> behaviours,
        CallbackInfo callbackInfo
    ) {
        SmartBlockEntity smartBlockEntity = (SmartBlockEntity) (Object) this;
        numiaerobridge$salePointBehaviour = new DockingConnectorSalePointBehaviour(
            smartBlockEntity,
            this
        );
        behaviours.add(numiaerobridge$salePointBehaviour);
    }

    @Inject(method = "write", at = @At("TAIL"), remap = false)
    private void numiaerobridge$writeMode(
        CompoundTag tag,
        HolderLookup.Provider registries,
        boolean clientPacket,
        CallbackInfo callbackInfo
    ) {
        tag.putBoolean("NumismaticsFluidMode", numiaerobridge$fluidMode);
    }

    @Inject(method = "read", at = @At("TAIL"), remap = false)
    private void numiaerobridge$readMode(
        CompoundTag tag,
        HolderLookup.Provider registries,
        boolean clientPacket,
        CallbackInfo callbackInfo
    ) {
        numiaerobridge$fluidMode = tag.getBoolean("NumismaticsFluidMode");
    }

    /**
     * Simulated exposes the paired inventory through AbstractContainer. Keep the original
     * container as the delegate, but route insertions into the SalePoint buffer while the
     * SalePoint owns this connector. The SalePoint purchase path writes directly to the
     * remote connector's local inventory and therefore bypasses this interception.
     */
    @Inject(method = "getInventory", at = @At("RETURN"), cancellable = true, remap = false)
    private void numiaerobridge$wrapInventory(CallbackInfoReturnable<?> callback) {
        Object original = callback.getReturnValue();
        if (original == null) return;

        try {
            Class<?> containerInterface = Class.forName(ABSTRACT_CONTAINER);
            if (!containerInterface.isInstance(original)) return;

            InvocationHandler handler = (proxy, method, args) -> {
                if (numiaerobridge$isSalePointControlled()
                    && !numiaerobridge$isFluidMode()
                    && args != null) {
                    String name = method.getName();

                    if ("insertGeneral".equals(name) && args.length == 3
                        && args[1] instanceof Integer amount
                        && args[2] instanceof Boolean simulate) {
                        return numiaerobridge$insertIntoSalePointBuffer(args[0], amount, simulate);
                    }

                    if ("insertSlot".equals(name) && args.length == 3
                        && args[0] instanceof ItemStack stack
                        && args[2] instanceof Boolean simulate) {
                        int inserted = numiaerobridge$copyToSalePointBuffer(stack, simulate);
                        ItemStack remainder = stack.copy();
                        remainder.shrink(inserted);
                        return remainder;
                    }

                    // Do not let another inventory pull unpurchased stock out of this port.
                    if ("extractGeneral".equals(name)) return 0;
                    if ("extractSlot".equals(name)) return ItemStack.EMPTY;
                }

                try {
                    return method.invoke(original, args);
                } catch (InvocationTargetException exception) {
                    throw exception.getCause();
                }
            };

            Object wrapped = Proxy.newProxyInstance(
                containerInterface.getClassLoader(),
                new Class<?>[]{containerInterface},
                handler
            );
            callback.setReturnValue(wrapped);
        } catch (ReflectiveOperationException | LinkageError exception) {
            NumismaticsAeronauticsBridge.LOGGER.error(
                "Could not wrap the Docking Connector inventory for SalePoint buffering.",
                exception
            );
        }
    }

    @Override
    public boolean numiaerobridge$isFluidMode() {
        return numiaerobridge$fluidMode;
    }

    @Override
    public boolean numiaerobridge$toggleMode() {
        if (numiaerobridge$salePointBehaviour != null
            && numiaerobridge$salePointBehaviour.isControlledBySalepoint()) {
            return false;
        }

        numiaerobridge$fluidMode = !numiaerobridge$fluidMode;
        numiaerobridge$notifyUpdate();
        return true;
    }

    @Override
    public boolean numiaerobridge$isSalePointControlled() {
        return numiaerobridge$salePointBehaviour != null
            && numiaerobridge$salePointBehaviour.isControlledBySalepoint()
            && (numiaerobridge$salePointBehaviour.isItemSaleActive()
                || numiaerobridge$salePointBehaviour.isFluidSaleActive());
    }

    @Override
    public Object numiaerobridge$getBoundState() {
        return numiaerobridge$salePointBehaviour == null
            ? null
            : numiaerobridge$salePointBehaviour.getBoundState();
    }

    @Unique
    private int numiaerobridge$insertIntoSalePointBuffer(Object itemInfo, int amount, boolean simulate)
        throws ReflectiveOperationException {
        Class<?> infoClass = Class.forName(ITEM_INFO_WRAPPER);
        Object stackObject = infoClass.getMethod("generateFromInfo", infoClass).invoke(null, itemInfo);
        if (!(stackObject instanceof ItemStack stack) || stack.isEmpty()) return 0;
        stack.setCount(amount);
        return numiaerobridge$copyToSalePointBuffer(stack, simulate);
    }

    @Unique
    @SuppressWarnings({"rawtypes", "unchecked"})
    private int numiaerobridge$copyToSalePointBuffer(ItemStack stack, boolean simulate)
        throws ReflectiveOperationException {
        Object state = numiaerobridge$getBoundState();
        if (state == null) return 0;

        Object buffer = state.getClass().getMethod("getBuffer").invoke(state);
        Method copy = buffer.getClass().getMethod("copyToBuffer", Object.class, boolean.class);
        int inserted = ((Number) copy.invoke(buffer, stack, simulate)).intValue();

        if (inserted > 0 && !simulate) {
            numiaerobridge$notifyUpdate();
        }
        return inserted;
    }

    @Unique
    private void numiaerobridge$notifyUpdate() {
        try {
            ((Object) this).getClass().getMethod("notifyUpdate").invoke(this);
        } catch (ReflectiveOperationException | LinkageError exception) {
            NumismaticsAeronauticsBridge.LOGGER.debug(
                "Could not notify a Docking Connector update.",
                exception
            );
        }
    }
}
