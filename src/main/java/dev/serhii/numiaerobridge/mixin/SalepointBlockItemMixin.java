package dev.serhii.numiaerobridge.mixin;

import dev.serhii.numiaerobridge.DockingConnectorSalePointAccess;
import net.minecraft.core.component.DataComponents;
import net.minecraft.network.chat.Component;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.context.UseOnContext;
import net.minecraft.world.level.Level;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/**
 * Sneak-right-clicking a connector with a fresh SalePoint item switches its binding mode.
 * A normal right-click then selects the connector as the SalePoint target.
 */
@Mixin(
    targets = "dev.ithundxr.createnumismatics.content.salepoint.SalepointBlockItem",
    remap = false
)
public abstract class SalepointBlockItemMixin {
    @Inject(method = "useOn", at = @At("HEAD"), cancellable = true, remap = false)
    private void numiaerobridge$toggleConnectorMode(
        UseOnContext context,
        CallbackInfoReturnable<InteractionResult> callback
    ) {
        Player player = context.getPlayer();
        if (player == null || !player.isShiftKeyDown()) return;

        ItemStack stack = context.getItemInHand();
        if (stack.has(DataComponents.CUSTOM_DATA)) return;

        Level level = context.getLevel();
        if (!(level.getBlockEntity(context.getClickedPos()) instanceof DockingConnectorSalePointAccess access)) {
            return;
        }

        if (level.isClientSide) {
            callback.setReturnValue(InteractionResult.SUCCESS);
            return;
        }

        if (!access.numiaerobridge$toggleMode()) {
            player.displayClientMessage(
                Component.literal("Спочатку відв'яжи SalePoint від цього конектора, щоб змінити режим."),
                true
            );
        } else {
            String mode = access.numiaerobridge$isFluidMode() ? "рідини" : "предмети";
            player.displayClientMessage(
                Component.literal("Режим Docking Connector: продаж " + mode + ". Тепер звичайним кліком вибери конектор."),
                true
            );
        }

        callback.setReturnValue(InteractionResult.SUCCESS);
    }
}
