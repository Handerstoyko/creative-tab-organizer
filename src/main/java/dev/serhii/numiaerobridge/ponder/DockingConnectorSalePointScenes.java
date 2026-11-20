package dev.serhii.numiaerobridge.ponder;

import com.simibubi.create.foundation.ponder.CreateSceneBuilder;
import net.createmod.catnip.math.Pointing;
import net.createmod.ponder.api.PonderPalette;
import net.createmod.ponder.api.scene.SceneBuilder;
import net.createmod.ponder.api.scene.SceneBuildingUtil;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.BlockStateProperties;

/** Ponder explanation for using a SalePoint with a Simulated Docking Connector pair. */
public final class DockingConnectorSalePointScenes {
    private static final ResourceLocation CONNECTOR_ID =
        ResourceLocation.fromNamespaceAndPath("simulated", "docking_connector");
    private static final ResourceLocation SALEPOINT_ID =
        ResourceLocation.fromNamespaceAndPath("numismatics", "salepoint");

    private DockingConnectorSalePointScenes() {
    }

    public static void salePoint(SceneBuilder builder, SceneBuildingUtil util) {
        CreateSceneBuilder scene = new CreateSceneBuilder(builder);
        scene.title("docking_connector_sale_point", "Selling items and fluids with SalePoints");
        scene.configureBasePlate(0, 0, 7);
        scene.scaleSceneView(0.85f);
        scene.showBasePlate();

        Block connector = BuiltInRegistries.BLOCK.get(CONNECTOR_ID);
        Block salePoint = BuiltInRegistries.BLOCK.get(SALEPOINT_ID);
        ItemStack salePointItem = new ItemStack(BuiltInRegistries.ITEM.get(SALEPOINT_ID));

        BlockPos left = util.grid().at(2, 1, 3);
        BlockPos right = util.grid().at(5, 1, 3);
        BlockPos sale = util.grid().at(3, 1, 1);

        BlockState leftState = connector.defaultBlockState();
        BlockState rightState = connector.defaultBlockState();
        if (leftState.hasProperty(BlockStateProperties.FACING)) {
            leftState = leftState.setValue(BlockStateProperties.FACING, Direction.EAST);
            rightState = rightState.setValue(BlockStateProperties.FACING, Direction.WEST);
        }

        scene.world().setBlock(left, leftState, false);
        scene.world().setBlock(right, rightState, false);
        scene.world().setBlock(sale, salePoint.defaultBlockState(), false);
        scene.world().showSection(util.select().layer(0), Direction.UP);
        scene.idle(5);
        scene.world().showSection(util.select().position(left), Direction.DOWN);
        scene.idle(5);
        scene.world().showSection(util.select().position(right), Direction.DOWN);
        scene.idle(15);

        scene.overlay().showText(75)
            .text("Without a SalePoint bound, the connected pair keeps its normal item and fluid transfer behaviour.")
            .attachKeyFrame()
            .placeNearTarget()
            .pointAt(util.vector().topOf(left));
        scene.idle(85);

        scene.overlay().showText(90)
            .text("Use a fresh SalePoint item and sneak-right-click the connector to switch between item and fluid sale modes.")
            .attachKeyFrame()
            .placeNearTarget()
            .pointAt(util.vector().topOf(left));
        scene.overlay().showControls(util.vector().topOf(left), Pointing.DOWN, 40)
            .rightClick()
            .withItem(salePointItem);
        scene.idle(95);

        scene.overlay().showText(90)
            .text("Then right-click the connector with the SalePoint item to select it as the target.")
            .attachKeyFrame()
            .placeNearTarget()
            .pointAt(util.vector().topOf(right));
        scene.overlay().showControls(util.vector().topOf(right), Pointing.DOWN, 40)
            .rightClick()
            .withItem(salePointItem);
        scene.idle(70);

        scene.world().showSection(util.select().position(sale), Direction.DOWN);
        scene.idle(10);
        scene.overlay().showLine(PonderPalette.GREEN,
                util.vector().centerOf(left), util.vector().centerOf(right), 50);
        scene.overlay().showText(110)
            .text("While bound, incoming stock is held in the SalePoint buffer instead of being delivered directly.")
            .attachKeyFrame()
            .placeNearTarget()
            .pointAt(util.vector().topOf(sale));
        scene.idle(120);

        scene.overlay().showText(110)
            .text("After a successful payment, the purchased items or fluid are transferred into the opposite connector.")
            .attachKeyFrame()
            .placeNearTarget()
            .pointAt(util.vector().topOf(right));
        scene.idle(120);

        scene.overlay().showText(85)
            .text("Removing the SalePoint releases the connector pair and restores normal transfer.")
            .attachKeyFrame()
            .placeNearTarget()
            .pointAt(util.vector().topOf(left));
        scene.idle(95);
    }
}
