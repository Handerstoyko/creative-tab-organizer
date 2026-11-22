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
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.BlockStateProperties;

import java.lang.reflect.Field;
import java.lang.reflect.Method;

/**
 * Ponder scenes for the Simulated Docking Connector / Numismatics SalePoint bridge.
 *
 * Docking Connectors are rendered almost entirely by Simulated's block-entity renderer.
 * Their visual extension/feet values therefore have to be initialized explicitly in
 * Ponder; a plain setBlock(defaultBlockState()) only shows the retracted base.
 */
public final class DockingConnectorSalePointScenes {
    private static final ResourceLocation CONNECTOR_ID =
        ResourceLocation.fromNamespaceAndPath("simulated", "docking_connector");
    private static final ResourceLocation SALEPOINT_ID =
        ResourceLocation.fromNamespaceAndPath("numismatics", "salepoint");
    private static final ResourceLocation WATER_BUCKET_ID =
        ResourceLocation.withDefaultNamespace("water_bucket");

    private DockingConnectorSalePointScenes() {
    }

    public static void basics(SceneBuilder builder, SceneBuildingUtil util) {
        CreateSceneBuilder scene = createScene(builder, "docking_connector_basics",
            "Docking Connectors keep their native transfer behaviour");
        Block connector = block(CONNECTOR_ID);
        BlockPos left = util.grid().at(2, 1, 3);
        BlockPos right = util.grid().at(5, 1, 3);

        placeConnector(scene, left, connector, Direction.EAST, true);
        placeConnector(scene, right, connector, Direction.WEST, true);
        showPair(scene, util, left, right);

        scene.overlay().showText(80)
            .text("A docked pair acts as one connection while both connector inventories and tanks remain independent.")
            .attachKeyFrame().placeNearTarget().pointAt(util.vector().topOf(left));
        scene.idle(90);

        scene.overlay().showLine(PonderPalette.GREEN,
            util.vector().centerOf(left), util.vector().centerOf(right), 60);
        scene.overlay().showText(85)
            .text("Without a SalePoint bound, items and fluids pass through the pair using the normal connector behaviour.")
            .attachKeyFrame().placeNearTarget().pointAt(util.vector().topOf(right));
        scene.idle(95);
    }

    public static void itemSale(SceneBuilder builder, SceneBuildingUtil util) {
        CreateSceneBuilder scene = createScene(builder, "docking_connector_item_sale",
            "Selling items through a SalePoint");
        Block connector = block(CONNECTOR_ID);
        Block salePoint = block(SALEPOINT_ID);
        ItemStack salePointItem = item(SALEPOINT_ID);
        BlockPos left = util.grid().at(2, 1, 3);
        BlockPos right = util.grid().at(5, 1, 3);
        BlockPos sale = util.grid().at(3, 1, 1);

        placeConnector(scene, left, connector, Direction.EAST, true);
        placeConnector(scene, right, connector, Direction.WEST, true);
        scene.world().setBlock(sale, salePoint.defaultBlockState(), false);
        showPair(scene, util, left, right);

        scene.overlay().showText(75)
            .text("Start with a fresh SalePoint item. Sneak-right-click a connector to switch its resource mode.")
            .attachKeyFrame().placeNearTarget().pointAt(util.vector().topOf(left));
        scene.overlay().showControls(util.vector().topOf(left), Pointing.DOWN, 45)
            .rightClick().withItem(salePointItem);
        scene.idle(85);

        scene.overlay().showText(80)
            .text("Right-click the connector with the selected SalePoint item to bind that connector pair as its target.")
            .attachKeyFrame().placeNearTarget().pointAt(util.vector().topOf(right));
        scene.overlay().showControls(util.vector().topOf(right), Pointing.DOWN, 45)
            .rightClick().withItem(salePointItem);
        scene.idle(90);

        scene.world().showSection(util.select().position(sale), Direction.DOWN);
        scene.idle(10);
        scene.overlay().showLine(PonderPalette.BLUE,
            util.vector().centerOf(left), util.vector().centerOf(right), 55);
        scene.overlay().showText(85)
            .text("While the SalePoint controls the pair, incoming items are stored in its buffer. They are not delivered to the buyer yet.")
            .attachKeyFrame().placeNearTarget().pointAt(util.vector().topOf(sale));
        scene.idle(95);

        scene.overlay().showControls(util.vector().topOf(sale), Pointing.DOWN, 50)
            .rightClick().withItem(salePointItem);
        scene.overlay().showText(90)
            .text("The order is completed only after payment succeeds. The purchased quantity is then inserted into the opposite connector.")
            .attachKeyFrame().placeNearTarget().pointAt(util.vector().topOf(right));
        scene.idle(100);

        scene.overlay().showText(75)
            .text("When the SalePoint is unbound, the pair returns to normal item transfer.")
            .attachKeyFrame().placeNearTarget().pointAt(util.vector().topOf(left));
        scene.idle(85);
    }

    public static void fluidSale(SceneBuilder builder, SceneBuildingUtil util) {
        CreateSceneBuilder scene = createScene(builder, "docking_connector_fluid_sale",
            "Selling fluids through a SalePoint");
        Block connector = block(CONNECTOR_ID);
        Block salePoint = block(SALEPOINT_ID);
        ItemStack salePointItem = item(SALEPOINT_ID);
        ItemStack waterBucket = item(WATER_BUCKET_ID);
        BlockPos left = util.grid().at(2, 1, 3);
        BlockPos right = util.grid().at(5, 1, 3);
        BlockPos sale = util.grid().at(3, 1, 1);

        placeConnector(scene, left, connector, Direction.EAST, true);
        placeConnector(scene, right, connector, Direction.WEST, true);
        scene.world().setBlock(sale, salePoint.defaultBlockState(), false);
        showPair(scene, util, left, right);

        scene.overlay().showText(80)
            .text("Use a fresh SalePoint item and sneak-right-click a connector to switch from item sales to fluid sales.")
            .attachKeyFrame().placeNearTarget().pointAt(util.vector().topOf(left));
        scene.overlay().showControls(util.vector().topOf(left), Pointing.DOWN, 45)
            .rightClick().withItem(salePointItem);
        scene.idle(90);

        scene.overlay().showText(80)
            .text("Right-click the connector again with the SalePoint item to select the pair as the sale target.")
            .attachKeyFrame().placeNearTarget().pointAt(util.vector().topOf(right));
        scene.overlay().showControls(util.vector().topOf(right), Pointing.DOWN, 45)
            .rightClick().withItem(salePointItem);
        scene.idle(90);

        scene.world().showSection(util.select().position(sale), Direction.DOWN);
        scene.idle(10);
        scene.overlay().showControls(util.vector().topOf(left), Pointing.DOWN, 45)
            .rightClick().withItem(waterBucket);
        scene.overlay().showText(85)
            .text("Incoming fluid is redirected into the SalePoint buffer. The connected connector tank does not receive it before payment.")
            .attachKeyFrame().placeNearTarget().pointAt(util.vector().topOf(sale));
        scene.idle(95);

        scene.overlay().showText(90)
            .text("After successful payment, only the ordered fluid amount is delivered to the opposite connector tank.")
            .attachKeyFrame().placeNearTarget().pointAt(util.vector().topOf(right));
        scene.idle(100);

        scene.overlay().showText(85)
            .text("Orders larger than 1 litre are supported. The SalePoint still delivers the requested amount only after payment.")
            .attachKeyFrame().placeNearTarget().pointAt(util.vector().topOf(sale));
        scene.idle(95);

        scene.overlay().showText(75)
            .text("Unbinding the SalePoint restores normal fluid transfer between the connectors.")
            .attachKeyFrame().placeNearTarget().pointAt(util.vector().topOf(left));
        scene.idle(85);
    }

    private static CreateSceneBuilder createScene(SceneBuilder builder, String id, String title) {
        CreateSceneBuilder scene = new CreateSceneBuilder(builder);
        scene.title(id, title);
        scene.configureBasePlate(0, 0, 7);
        scene.setSceneOffsetY(-0.5f);
        scene.scaleSceneView(0.85f);
        scene.showBasePlate();
        scene.idle(5);
        return scene;
    }

    private static void placeConnector(CreateSceneBuilder scene, BlockPos pos, Block block,
                                       Direction facing, boolean linked) {
        BlockState state = block.defaultBlockState();
        if (state.hasProperty(BlockStateProperties.FACING))
            state = state.setValue(BlockStateProperties.FACING, facing);
        if (state.hasProperty(BlockStateProperties.POWERED))
            state = state.setValue(BlockStateProperties.POWERED, true);
        if (state.hasProperty(BlockStateProperties.EXTENDED))
            state = state.setValue(BlockStateProperties.EXTENDED, true);

        scene.world().setBlock(pos, state, false);
        // Simulated renders the connector's pistons and feet in its BER, not in the
        // static block model. Initialize the visual interpolation values explicitly.
        scene.world().modifyBlockEntity(pos, BlockEntity.class,
            be -> initializeConnectorVisual(be, linked));
    }

    private static void initializeConnectorVisual(BlockEntity blockEntity, boolean linked) {
        try {
            setBooleanField(blockEntity, "powered", true);
            setLerpedFloat(blockEntity, "extension", 1.0);
            setLerpedFloat(blockEntity, "feet", linked ? 1.0 : 0.0);
        } catch (ReflectiveOperationException ignored) {
            // Keep the scene usable if a future Simulated version changes its BE internals.
        }
    }

    private static void setBooleanField(Object target, String name, boolean value)
        throws ReflectiveOperationException {
        Field field = findField(target.getClass(), name);
        field.setAccessible(true);
        field.setBoolean(target, value);
    }

    private static void setLerpedFloat(Object target, String name, double value)
        throws ReflectiveOperationException {
        Field field = findField(target.getClass(), name);
        field.setAccessible(true);
        Object lerpedFloat = field.get(target);
        Method startWithValue = lerpedFloat.getClass().getMethod("startWithValue", double.class);
        startWithValue.invoke(lerpedFloat, value);
    }

    private static Field findField(Class<?> type, String name) throws NoSuchFieldException {
        Class<?> current = type;
        while (current != null) {
            try {
                return current.getDeclaredField(name);
            } catch (NoSuchFieldException ignored) {
                current = current.getSuperclass();
            }
        }
        throw new NoSuchFieldException(name);
    }

    private static void showPair(CreateSceneBuilder scene, SceneBuildingUtil util,
                                 BlockPos left, BlockPos right) {
        scene.world().showSection(util.select().layer(0), Direction.UP);
        scene.idle(5);
        scene.world().showSection(util.select().position(left), Direction.DOWN);
        scene.idle(5);
        scene.world().showSection(util.select().position(right), Direction.DOWN);
        scene.idle(12);
        scene.overlay().showLine(PonderPalette.GREEN,
            util.vector().centerOf(left), util.vector().centerOf(right), 45);
        scene.idle(10);
    }

    private static Block block(ResourceLocation id) {
        return BuiltInRegistries.BLOCK.get(id);
    }

    private static ItemStack item(ResourceLocation id) {
        return new ItemStack(BuiltInRegistries.ITEM.get(id));
    }
}
