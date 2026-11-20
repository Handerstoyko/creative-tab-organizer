package dev.serhii.numiaerobridge.mixin;

import dev.serhii.numiaerobridge.DockingConnectorSalePointAccess;
import dev.serhii.numiaerobridge.NumismaticsAeronauticsBridge;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Coerce;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.List;

/**
 * Redirects incoming Docking Connector fluid to the active Numismatics buffer.
 * The connector's normal linked-tank transfer is bypassed until the purchase succeeds.
 */
@Mixin(
    targets = "dev.simulated_team.simulated.content.blocks.docking_connector.DockingConnectorTank",
    remap = false
)
public abstract class DockingConnectorTankMixin {
    @Inject(
        method = "insert(Ldev/simulated_team/simulated/multiloader/tanks/CFluidType;JZLjava/lang/Runnable;)J",
        at = @At("HEAD"),
        cancellable = true,
        remap = false
    )
    private void numiaerobridge$captureFluid(
        @Coerce Object fluidType,
        long amount,
        boolean simulate,
        Runnable beforeApply,
        CallbackInfoReturnable<Long> callback
    ) {
        try {
            Object owner = getField(this, "blockEntity");
            if (!(owner instanceof DockingConnectorSalePointAccess access)) {
                return;
            }

            // Fluid may be pumped into either connector. The pair resolves the SalePoint
            // on either end and captures the flow into that SalePoint's buffer.
            Object state = access.numiaerobridge$getActiveSalePointState(true);
            // No active fluid SalePoint: let Docking Connector perform its normal tank transfer.
            if (state == null) return;

            Object buffer = state.getClass().getMethod("getBuffer").invoke(state);
            Object helper = getSingleTankWrapper();
            Method fromCType = findMethod(helper, "fromCType", 2);
            Object fluidStack = fromCType.invoke(null, fluidType, (int) Math.min(Integer.MAX_VALUE, amount));

            Object action = fluidAction(simulate ? "SIMULATE" : "EXECUTE");
            Method fill = findFillMethod(buffer, fluidStack);
            if (!simulate && beforeApply != null) {
                beforeApply.run();
            }

            int accepted = ((Number) fill.invoke(buffer, fluidStack, action)).intValue();
            callback.setReturnValue((long) accepted);
            if (accepted > 0 && !simulate) {
                try {
                    owner.getClass().getMethod("notifyUpdate").invoke(owner);
                } catch (ReflectiveOperationException ignored) {
                    // Buffer listeners already mark the SalePoint state dirty.
                }
            }
        } catch (ReflectiveOperationException | LinkageError exception) {
            NumismaticsAeronauticsBridge.LOGGER.error(
                "Could not capture incoming fluid for a Docking Connector SalePoint; blocking the transfer to prevent unpaid delivery.",
                exception
            );
            callback.setReturnValue(0L);
        }
    }

    private static Object getSingleTankWrapper() throws ClassNotFoundException {
        for (String name : List.of(
            "dev.simulated_team.simulated.multiloader.tanks.neoforge.SingleTankWrapper",
            "dev.simulated_team.simulated.multiloader.tanks.forge.SingleTankWrapper"
        )) {
            try {
                return Class.forName(name);
            } catch (ClassNotFoundException ignored) {
            }
        }
        throw new ClassNotFoundException("Simulated SingleTankWrapper was not found.");
    }

    private static Object fluidAction(String name) throws ClassNotFoundException {
        for (String className : List.of(
            "net.neoforged.neoforge.fluids.capability.IFluidHandler$FluidAction",
            "net.minecraftforge.fluids.capability.IFluidHandler$FluidAction"
        )) {
            try {
                Class<?> actionClass = Class.forName(className);
                @SuppressWarnings({"rawtypes", "unchecked"})
                Object value = Enum.valueOf((Class<? extends Enum>) actionClass, name);
                return value;
            } catch (ClassNotFoundException ignored) {
            }
        }
        throw new ClassNotFoundException("NeoForge/Forge FluidAction was not found.");
    }

    private static Method findMethod(Object target, String name, int parameterCount) throws NoSuchMethodException {
        for (Method method : ((Class<?>) target).getMethods()) {
            if (method.getName().equals(name) && method.getParameterCount() == parameterCount) {
                return method;
            }
        }
        throw new NoSuchMethodException(name);
    }

    private static Method findFillMethod(Object buffer, Object fluidStack) throws NoSuchMethodException {
        for (Method method : buffer.getClass().getMethods()) {
            if (method.getName().equals("fill")
                && method.getParameterCount() == 2
                && method.getParameterTypes()[0].isInstance(fluidStack)
                && method.getParameterTypes()[1].isEnum()) {
                return method;
            }
        }
        throw new NoSuchMethodException("Fluid buffer fill(FluidStack, FluidAction)");
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
}
