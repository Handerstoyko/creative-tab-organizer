package dev.serhii.numiaerobridge.mixin;

import dev.ithundxr.createnumismatics.content.salepoint.behaviours.SalepointTargetBehaviour;
import dev.ithundxr.createnumismatics.content.salepoint.states.ISalepointState;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.Level;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

import com.simibubi.create.foundation.blockEntity.behaviour.BlockEntityBehaviour;

/**
 * Releases the target before Numismatics starts destroying/unloading the SalePoint block entity.
 *
 * Numismatics also releases the target from its destroy() implementation, but doing it here
 * makes the cleanup happen before its superclass cleanup and before the block entity is removed
 * from the level. This prevents a Docking Connector from retaining an obsolete SalePoint lock.
 */
@Mixin(
    targets = "dev.ithundxr.createnumismatics.content.salepoint.SalepointBlockEntity",
    remap = false
)
public abstract class SalepointBlockEntityMixin {
    private static final Logger LOGGER = LoggerFactory.getLogger("Numismatics Aeronautics Bridge");

    @Inject(method = "destroy", at = @At("HEAD"), remap = false)
    private void numiaerobridge$releaseTargetBeforeDestroy(CallbackInfo callbackInfo) {
        numiaerobridge$releaseTarget();
    }

    @Inject(method = "remove", at = @At("HEAD"), remap = false)
    private void numiaerobridge$releaseTargetBeforeRemove(CallbackInfo callbackInfo) {
        numiaerobridge$releaseTarget();
    }

    private void numiaerobridge$releaseTarget() {
        try {
            Object levelObject = ((Object) this).getClass().getMethod("getLevel").invoke(this);
            Object targetObject = ((Object) this).getClass().getMethod("getTargetedPos").invoke(this);
            Object stateObject = ((Object) this).getClass().getMethod("getSalepointState").invoke(this);

            if (!(levelObject instanceof Level level)
                || level.isClientSide
                || !(targetObject instanceof BlockPos targetPos)
                || !(stateObject instanceof ISalepointState<?> state)) {
                return;
            }

            SalepointTargetBehaviour<?> target = BlockEntityBehaviour.get(
                level,
                targetPos,
                SalepointTargetBehaviour.TYPE
            );
            if (target != null) {
                @SuppressWarnings({"rawtypes", "unchecked"})
                SalepointTargetBehaviour rawTarget = target;
                rawTarget.relinquishControl(state);
            }
        } catch (ReflectiveOperationException | LinkageError exception) {
            LOGGER.error("Could not release a Docking Connector from a removed SalePoint.", exception);
        }
    }
}
