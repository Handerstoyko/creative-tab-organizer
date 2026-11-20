package dev.serhii.numiaerobridge.mixin;

import com.simibubi.create.foundation.blockEntity.SmartBlockEntity;
import com.simibubi.create.foundation.blockEntity.behaviour.BlockEntityBehaviour;
import dev.ithundxr.createnumismatics.content.salepoint.behaviours.ItemSalepointTargetBehaviour;
import dev.ithundxr.createnumismatics.content.salepoint.behaviours.SalepointTargetBehaviour.PurchaseProvider;
import dev.ithundxr.createnumismatics.content.salepoint.states.ISalepointState;
import dev.serhii.numiaerobridge.NumismaticsAeronauticsBridge;
import net.minecraft.core.HolderLookup;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.item.ItemEntity;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.Vec3;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.List;

/**
 * Adds Numismatics' item SalePoint target behaviour to Aeronautics' Docking Connector.
 *
 * The target is named as a string deliberately: the connector belongs to the bundled
 * Simulated module, so the addon does not need to compile against Sable/Simulated internals.
 */
@Mixin(
    targets = "dev.simulated_team.simulated.content.blocks.docking_connector.DockingConnectorBlockEntity",
    remap = false
)
public abstract class DockingConnectorBlockEntityMixin {
    private static final String ITEM_INFO_WRAPPER =
        "dev.simulated_team.simulated.multiloader.inventory.ItemInfoWrapper";

    @Inject(method = "addBehaviours", at = @At("TAIL"), remap = false)
    private void numiaerobridge$addSalePointBehaviour(
        List<BlockEntityBehaviour> behaviours,
        CallbackInfo callbackInfo
    ) {
        SmartBlockEntity connectorBlockEntity = (SmartBlockEntity) (Object) this;
        Object connector = this;

        behaviours.add(new ItemSalepointTargetBehaviour(connectorBlockEntity) {
            private boolean underSalePointControl;
            private ISalepointState<ItemStack> boundState;

            @Override
            protected boolean isUnderControlInternal(ISalepointState<ItemStack> state) {
                return underSalePointControl;
            }

            @Override
            protected void ensureUnderControlInternal(ISalepointState<ItemStack> state) {
                boundState = state;
                if (!underSalePointControl) {
                    underSalePointControl = true;
                    connectorBlockEntity.notifyUpdate();
                }
            }

            @Override
            protected void relinquishControlInternal(ISalepointState<ItemStack> state) {
                underSalePointControl = false;
                boundState = null;
                connectorBlockEntity.notifyUpdate();
            }

            @Override
            public boolean hasSpaceFor(ItemStack object) {
                if (!underSalePointControl || object.isEmpty()) {
                    return false;
                }

                try {
                    return canInsert(connector, object, true) == object.getCount();
                } catch (ReflectiveOperationException | LinkageError exception) {
                    NumismaticsAeronauticsBridge.LOGGER.error(
                        "Could not inspect the Docking Connector inventory.",
                        exception
                    );
                    return false;
                }
            }

            @Override
            public boolean doPurchase(
                ItemStack object,
                PurchaseProvider<ItemStack> purchaseProvider
            ) {
                if (!hasSpaceFor(object)) {
                    return false;
                }

                List<ItemStack> extracted = purchaseProvider.extract();
                if (extracted.isEmpty()) {
                    return false;
                }

                ItemStack combined = combineCompatibleStacks(extracted);
                if (combined.isEmpty()) {
                    refund(extracted);
                    return false;
                }

                try {
                    int simulated = canInsert(connector, combined, true);
                    if (simulated != combined.getCount()) {
                        refund(extracted);
                        return false;
                    }

                    int inserted = canInsert(connector, combined, false);
                    if (inserted == combined.getCount()) {
                        return true;
                    }

                    // In the unlikely event that the inventory changed between simulation and
                    // insertion, remove any partial insertion before returning the goods.
                    if (inserted > 0) {
                        int rolledBack = extractFromReceiver(connector, combined, inserted);
                        if (rolledBack != inserted) {
                            NumismaticsAeronauticsBridge.LOGGER.error(
                                "Docking Connector insertion changed after simulation; rollback was partial."
                            );
                        }
                    }

                    refund(extracted);
                    return false;
                } catch (ReflectiveOperationException | LinkageError exception) {
                    NumismaticsAeronauticsBridge.LOGGER.error(
                        "Docking Connector purchase transfer failed; returning the items to the SalePoint.",
                        exception
                    );
                    refund(extracted);
                    return false;
                }
            }

            @Override
            public void read(
                CompoundTag tag,
                HolderLookup.Provider registries,
                boolean clientPacket
            ) {
                super.read(tag, registries, clientPacket);
                underSalePointControl = tag.getBoolean("NumismaticsSalePointUnderControl");
            }

            @Override
            public void write(
                CompoundTag tag,
                HolderLookup.Provider registries,
                boolean clientPacket
            ) {
                super.write(tag, registries, clientPacket);
                tag.putBoolean("NumismaticsSalePointUnderControl", underSalePointControl);
            }

            private void refund(List<ItemStack> stacks) {
                for (ItemStack original : stacks) {
                    if (original.isEmpty()) {
                        continue;
                    }

                    ItemStack remainder = original.copy();
                    if (boundState != null) {
                        int returned = boundState.getBuffer().copyToBuffer(remainder);
                        remainder.shrink(returned);
                    }

                    if (!remainder.isEmpty()) {
                        dropAtConnector(connectorBlockEntity.getLevel(), connectorBlockEntity.getBlockPos().getCenter(), remainder);
                    }
                }
            }
        });
    }

    /**
     * The Docking Connector exposes its inventory through Simulated's AbstractContainer API.
     * Reflection keeps this bridge independent of Simulated's implementation classes.
     */
    private static int canInsert(Object connector, ItemStack stack, boolean simulate)
        throws ReflectiveOperationException {
        Object inventory = getPairedInventory(connector);
        if (inventory == null) {
            return 0;
        }

        ItemStack current = (ItemStack) inventory.getClass()
            .getMethod("getItem", int.class)
            .invoke(inventory, 0);

        if (!current.isEmpty() && !ItemStack.isSameItemSameComponents(current, stack)) {
            return 0;
        }

        Class<?> infoClass = Class.forName(ITEM_INFO_WRAPPER);
        Object info = infoClass.getMethod("generateFromStack", ItemStack.class).invoke(null, stack);
        Method insert = inventory.getClass().getMethod(
            "insertGeneral",
            infoClass,
            int.class,
            boolean.class
        );

        return ((Number) insert.invoke(inventory, info, stack.getCount(), simulate)).intValue();
    }

    private static int extractFromReceiver(Object connector, ItemStack stack, int amount)
        throws ReflectiveOperationException {
        Object other = invokeNoArgs(connector, "getOtherConnector");
        if (other == null) {
            return 0;
        }

        // Calling getInventory() on the receiving connector also refreshes its docked inventory
        // state, which is required by Simulated's one-slot insertion gate.
        Object receiverInventory = invokeNoArgs(other, "getInventory");
        Class<?> infoClass = Class.forName(ITEM_INFO_WRAPPER);
        Object info = infoClass.getMethod("generateFromStack", ItemStack.class).invoke(null, stack);
        Method extract = receiverInventory.getClass().getMethod(
            "extractGeneral",
            infoClass,
            int.class,
            boolean.class
        );

        return ((Number) extract.invoke(receiverInventory, info, amount, false)).intValue();
    }

    private static Object getPairedInventory(Object connector) throws ReflectiveOperationException {
        Object other = invokeNoArgs(connector, "getOtherConnector");
        if (other == null) {
            return null;
        }

        boolean thisLocked = Boolean.TRUE.equals(invokeNoArgs(connector, "isLocked"));
        boolean otherLocked = Boolean.TRUE.equals(invokeNoArgs(other, "isLocked"));
        if (!thisLocked || !otherLocked) {
            return null;
        }

        // Dock both ends before asking this connector for the paired inventory.
        invokeNoArgs(other, "getInventory");
        return invokeNoArgs(connector, "getInventory");
    }

    private static Object invokeNoArgs(Object target, String methodName)
        throws ReflectiveOperationException {
        return target.getClass().getMethod(methodName).invoke(target);
    }

    private static ItemStack combineCompatibleStacks(List<ItemStack> stacks) {
        ItemStack combined = ItemStack.EMPTY;

        for (ItemStack stack : stacks) {
            if (stack.isEmpty()) {
                continue;
            }

            if (combined.isEmpty()) {
                combined = stack.copy();
                continue;
            }

            if (!ItemStack.isSameItemSameComponents(combined, stack)) {
                return ItemStack.EMPTY;
            }

            int nextCount = combined.getCount() + stack.getCount();
            if (nextCount > combined.getMaxStackSize()) {
                return ItemStack.EMPTY;
            }
            combined.setCount(nextCount);
        }

        return combined;
    }

    private static void dropAtConnector(Level level, Vec3 position, ItemStack stack) {
        if (!(level instanceof ServerLevel serverLevel) || stack.isEmpty()) {
            return;
        }

        ItemEntity itemEntity = new ItemEntity(
            serverLevel,
            position.x,
            position.y,
            position.z,
            stack
        );
        serverLevel.addFreshEntity(itemEntity);
    }
}
