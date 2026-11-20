package dev.serhii.numiaerobridge;

import com.simibubi.create.foundation.blockEntity.SmartBlockEntity;
import dev.ithundxr.createnumismatics.content.salepoint.behaviours.SalepointTargetBehaviour;
import dev.ithundxr.createnumismatics.content.salepoint.states.ISalepointState;
import dev.ithundxr.createnumismatics.content.salepoint.states.SalepointTypes;
import dev.ithundxr.createnumismatics.multiloader.fluid.MultiloaderFluidStack;
import net.minecraft.core.HolderLookup;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.item.ItemEntity;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.Vec3;

import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.List;

/**
 * A single Numismatics target behaviour whose content type is selected on the connector.
 * Numismatics uses one BehaviourType key per SmartBlockEntity, so item/fluid modes share
 * this behaviour instance rather than attempting to register two colliding behaviours.
 */
public final class DockingConnectorSalePointBehaviour extends SalepointTargetBehaviour<Object> {
    private static final String ITEM_INFO_WRAPPER =
        "dev.simulated_team.simulated.multiloader.inventory.ItemInfoWrapper";
    private static final String SINGLE_TANK =
        "dev.simulated_team.simulated.multiloader.tanks.SingleTank";
    private static final String SINGLE_TANK_WRAPPER_NEOfORGE =
        "dev.simulated_team.simulated.multiloader.tanks.neoforge.SingleTankWrapper";
    private static final String SINGLE_TANK_WRAPPER_FORGE =
        "dev.simulated_team.simulated.multiloader.tanks.forge.SingleTankWrapper";

    private final DockingConnectorSalePointAccess connector;
    private boolean underControl;
    private ISalepointState<?> boundState;

    public DockingConnectorSalePointBehaviour(SmartBlockEntity blockEntity, DockingConnectorSalePointAccess connector) {
        super(blockEntity);
        this.connector = connector;
    }

    @Override
    protected ISalepointState<?> tryBindToSalepointInternal() {
        return connector.numiaerobridge$isFluidMode()
            ? SalepointTypes.FLUID.create()
            : SalepointTypes.ITEM.create();
    }

    @SuppressWarnings("unchecked")
    @Override
    protected Class<Object> getContentType() {
        return (Class<Object>) (Class<?>) (connector.numiaerobridge$isFluidMode()
            ? MultiloaderFluidStack.class
            : ItemStack.class);
    }

    @Override
    protected boolean isUnderControlInternal(ISalepointState<Object> state) {
        return underControl && boundState == state;
    }

    @Override
    protected void ensureUnderControlInternal(ISalepointState<Object> state) {
        boundState = state;
        if (!underControl) {
            underControl = true;
            notifyConnector();
        }
    }

    @Override
    protected void relinquishControlInternal(ISalepointState<Object> state) {
        underControl = false;
        boundState = null;
        notifyConnector();
    }

    public ISalepointState<?> getBoundState() {
        return boundState;
    }

    public boolean isItemSaleActive() {
        return !connector.numiaerobridge$isFluidMode()
            && underControl
            && boundState != null
            && isControlledBySalepoint();
    }

    public boolean isFluidSaleActive() {
        return connector.numiaerobridge$isFluidMode()
            && underControl
            && boundState != null
            && isControlledBySalepoint();
    }

    @Override
    public boolean hasSpaceFor(Object object) {
        try {
            if (object instanceof ItemStack stack) {
                return !stack.isEmpty() && simulateItemDelivery(stack) == stack.getCount();
            }
            if (object instanceof MultiloaderFluidStack fluid) {
                return !fluid.isEmpty() && simulateFluidDelivery(fluid) == fluid.getAmount();
            }
        } catch (ReflectiveOperationException | LinkageError exception) {
            NumismaticsAeronauticsBridge.LOGGER.error("Could not check Docking Connector sale capacity.", exception);
        }
        return false;
    }

    @Override
    public boolean doPurchase(Object object, PurchaseProvider<Object> purchaseProvider) {
        if (object instanceof ItemStack) {
            return purchaseItems(purchaseProvider);
        }
        if (object instanceof MultiloaderFluidStack) {
            return purchaseFluid(purchaseProvider);
        }
        return false;
    }

    @Override
    public void read(CompoundTag tag, HolderLookup.Provider registries, boolean clientPacket) {
        super.read(tag, registries, clientPacket);
        underControl = tag.getBoolean("NumismaticsSalePointUnderControl");
    }

    @Override
    public void write(CompoundTag tag, HolderLookup.Provider registries, boolean clientPacket) {
        super.write(tag, registries, clientPacket);
        tag.putBoolean("NumismaticsSalePointUnderControl", underControl);
    }

    private boolean purchaseItems(PurchaseProvider<Object> provider) {
        List<Object> extracted = provider.extract();
        if (extracted.isEmpty()) return false;

        Object receiverInventory = null;
        try {
            Object receiver = getLockedPeer();
            if (receiver == null) {
                refundItems(extracted);
                return false;
            }

            receiverInventory = getField(receiver, "inventory");
            invoke(receiverInventory, "dock");
            int insertedTotal = 0;

            for (Object entry : extracted) {
                if (!(entry instanceof ItemStack stack) || stack.isEmpty()) {
                    rollbackItems(receiverInventory, extracted, insertedTotal);
                    return false;
                }
                int inserted = insertIntoInventory(receiverInventory, stack, false);
                insertedTotal += inserted;
                if (inserted != stack.getCount()) {
                    rollbackItems(receiverInventory, extracted, insertedTotal);
                    return false;
                }
            }

            notifyConnector();
            notifyObject(receiver);
            return true;
        } catch (ReflectiveOperationException | LinkageError exception) {
            NumismaticsAeronauticsBridge.LOGGER.error(
                "Docking Connector item purchase failed; returning stock to the SalePoint.", exception);
            if (receiverInventory != null) {
                rollbackItems(receiverInventory, extracted, 0);
            } else {
                refundItems(extracted);
            }
            return false;
        }
    }

    private boolean purchaseFluid(PurchaseProvider<Object> provider) {
        List<Object> extracted = provider.extract();
        if (extracted.isEmpty()) return false;

        try {
            Object receiver = getLockedPeer();
            if (receiver == null) {
                refundFluids(extracted);
                return false;
            }

            Object destinationTank = getField(receiver, "tank");
            long totalAmount = 0;
            Object commonType = null;
            for (Object entry : extracted) {
                if (!(entry instanceof MultiloaderFluidStack fluid) || fluid.isEmpty()) {
                    refundFluids(extracted);
                    return false;
                }
                Object type = toConnectorFluidType(fluid);
                if (commonType == null) commonType = type;
                else if (!commonType.equals(type)) {
                    refundFluids(extracted);
                    return false;
                }
                totalAmount += fluid.getAmount();
            }

            if (commonType == null || calculateTankInsert(destinationTank, commonType, totalAmount) != totalAmount) {
                refundFluids(extracted);
                return false;
            }

            for (Object entry : extracted) {
                MultiloaderFluidStack fluid = (MultiloaderFluidStack) entry;
                Object type = toConnectorFluidType(fluid);
                applyTankInsert(destinationTank, type, fluid.getAmount());
            }

            notifyConnector();
            notifyObject(receiver);
            return true;
        } catch (ReflectiveOperationException | LinkageError exception) {
            NumismaticsAeronauticsBridge.LOGGER.error(
                "Docking Connector fluid purchase failed; returning stock to the SalePoint.", exception);
            refundFluids(extracted);
            return false;
        }
    }

    private int simulateItemDelivery(ItemStack stack) throws ReflectiveOperationException {
        Object receiver = getLockedPeer();
        if (receiver == null) return 0;
        Object inventory = getField(receiver, "inventory");
        invoke(inventory, "dock");
        return insertIntoInventory(inventory, stack, true);
    }

    private long simulateFluidDelivery(MultiloaderFluidStack fluid) throws ReflectiveOperationException {
        Object receiver = getLockedPeer();
        if (receiver == null) return 0;
        Object destinationTank = getField(receiver, "tank");
        Object type = toConnectorFluidType(fluid);
        return calculateTankInsert(destinationTank, type, fluid.getAmount());
    }

    private Object getLockedPeer() throws ReflectiveOperationException {
        Object peer = invoke(blockEntity, "getOtherConnector");
        if (peer == null) return null;
        if (!Boolean.TRUE.equals(invoke(blockEntity, "isLocked"))
            || !Boolean.TRUE.equals(invoke(peer, "isLocked"))) {
            return null;
        }
        return peer;
    }

    private static int insertIntoInventory(Object inventory, ItemStack stack, boolean simulate)
        throws ReflectiveOperationException {
        Class<?> infoClass = Class.forName(ITEM_INFO_WRAPPER);
        Object info = infoClass.getMethod("generateFromStack", ItemStack.class).invoke(null, stack);
        Method insert = inventory.getClass().getMethod("insertGeneral", infoClass, int.class, boolean.class);
        return ((Number) insert.invoke(inventory, info, stack.getCount(), simulate)).intValue();
    }

    private static int extractFromInventory(Object inventory, ItemStack stack, int amount)
        throws ReflectiveOperationException {
        Class<?> infoClass = Class.forName(ITEM_INFO_WRAPPER);
        Object info = infoClass.getMethod("generateFromStack", ItemStack.class).invoke(null, stack);
        Method extract = inventory.getClass().getMethod("extractGeneral", infoClass, int.class, boolean.class);
        return ((Number) extract.invoke(inventory, info, amount, false)).intValue();
    }

    private void rollbackItems(Object receiverInventory, List<Object> extracted, int insertedTotal) {
        int remainingInserted = insertedTotal;
        for (Object entry : extracted) {
            if (!(entry instanceof ItemStack stack) || stack.isEmpty()) continue;
            int insertedFromThisStack = Math.min(remainingInserted, stack.getCount());
            remainingInserted -= insertedFromThisStack;

            int rolledBack = 0;
            if (insertedFromThisStack > 0 && receiverInventory != null) {
                try {
                    rolledBack = extractFromInventory(receiverInventory, stack, insertedFromThisStack);
                } catch (ReflectiveOperationException | LinkageError exception) {
                    NumismaticsAeronauticsBridge.LOGGER.error("Could not roll back a partial item delivery.", exception);
                }
            }

            int refundable = stack.getCount() - insertedFromThisStack + rolledBack;
            if (refundable > 0) {
                ItemStack refund = stack.copy();
                refund.setCount(refundable);
                refundItem(refund);
            }
        }
    }

    private void refundItems(List<Object> extracted) {
        for (Object entry : extracted) {
            if (entry instanceof ItemStack stack && !stack.isEmpty()) refundItem(stack);
        }
    }

    private void refundItem(ItemStack stack) {
        int returned = 0;
        try {
            if (boundState != null) {
                @SuppressWarnings("rawtypes")
                dev.ithundxr.createnumismatics.content.salepoint.containers.InvalidatableAbstractBuffer buffer =
                    boundState.getBuffer();
                returned = buffer.copyToBuffer(stack.copy(), false);
            }
        } catch (RuntimeException exception) {
            NumismaticsAeronauticsBridge.LOGGER.error("Could not return item stock to the SalePoint buffer.", exception);
        }

        if (returned < stack.getCount()) {
            ItemStack remainder = stack.copy();
            remainder.shrink(returned);
            dropAtConnector(remainder);
        }
    }

    private void refundFluids(List<Object> extracted) {
        if (boundState == null) return;
        @SuppressWarnings("rawtypes")
        dev.ithundxr.createnumismatics.content.salepoint.containers.InvalidatableAbstractBuffer buffer =
            boundState.getBuffer();
        for (Object entry : extracted) {
            if (entry instanceof MultiloaderFluidStack fluid && !fluid.isEmpty()) {
                try {
                    int returned = buffer.copyToBuffer(fluid.copy(), false);
                    if (returned < fluid.getAmount()) {
                        NumismaticsAeronauticsBridge.LOGGER.error(
                            "The SalePoint fluid buffer could not accept the full fluid refund ({} mB).",
                            fluid.getAmount() - returned
                        );
                    }
                } catch (RuntimeException exception) {
                    NumismaticsAeronauticsBridge.LOGGER.error("Could not return fluid stock to the SalePoint buffer.", exception);
                }
            }
        }
    }

    private Object toConnectorFluidType(MultiloaderFluidStack fluid) throws ReflectiveOperationException {
        Object wrapped = fluid.getClass().getMethod("getWrapped").invoke(fluid);
        ClassNotFoundException last = null;
        for (String helperName : List.of(SINGLE_TANK_WRAPPER_NEOfORGE, SINGLE_TANK_WRAPPER_FORGE)) {
            try {
                Class<?> helper = Class.forName(helperName);
                return helper.getMethod("toCType", wrapped.getClass()).invoke(null, wrapped);
            } catch (ClassNotFoundException exception) {
                last = exception;
            } catch (NoSuchMethodException exception) {
                // Try a loader variant with a different mapped FluidStack signature.
            }
        }
        if (last != null) throw last;
        throw new NoSuchMethodException("No Simulated SingleTankWrapper.toCType implementation was found.");
    }

    private static long calculateTankInsert(Object tank, Object type, long amount)
        throws ReflectiveOperationException {
        Class<?> singleTank = Class.forName(SINGLE_TANK);
        Method method = singleTank.getMethod("calculateInsert", singleTank, type.getClass(), long.class);
        return ((Number) method.invoke(null, tank, type, amount)).longValue();
    }

    private static void applyTankInsert(Object tank, Object type, long amount)
        throws ReflectiveOperationException {
        Class<?> singleTank = Class.forName(SINGLE_TANK);
        Method method = singleTank.getMethod("applyInsert", singleTank, type.getClass(), long.class);
        method.invoke(null, tank, type, amount);
    }

    private static Object getField(Object target, String name) throws ReflectiveOperationException {
        Class<?> type = target.getClass();
        while (type != null) {
            try {
                Field field = type.getDeclaredField(name);
                field.setAccessible(true);
                return field.get(target);
            } catch (NoSuchFieldException exception) {
                type = type.getSuperclass();
            }
        }
        throw new NoSuchFieldException(name);
    }

    private static Object invoke(Object target, String name) throws ReflectiveOperationException {
        return target.getClass().getMethod(name).invoke(target);
    }

    private void notifyConnector() {
        notifyObject(blockEntity);
    }

    private static void notifyObject(Object object) {
        try {
            invoke(object, "notifyUpdate");
        } catch (ReflectiveOperationException | LinkageError exception) {
            NumismaticsAeronauticsBridge.LOGGER.debug("A connector update notification was unavailable.", exception);
        }
    }

    private void dropAtConnector(ItemStack stack) {
        if (stack.isEmpty()) return;
        Level level = blockEntity.getLevel();
        if (!(level instanceof ServerLevel serverLevel)) return;
        Vec3 position = blockEntity.getBlockPos().getCenter();
        serverLevel.addFreshEntity(new ItemEntity(serverLevel, position.x, position.y, position.z, stack));
    }
}
