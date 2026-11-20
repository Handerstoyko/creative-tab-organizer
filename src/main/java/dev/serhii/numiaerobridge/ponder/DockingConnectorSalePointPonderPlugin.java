package dev.serhii.numiaerobridge.ponder;

import net.createmod.ponder.api.registration.PonderPlugin;
import net.createmod.ponder.api.registration.PonderSceneRegistrationHelper;
import net.minecraft.resources.ResourceLocation;

/** Adds the SalePoint integration storyboard to the Simulated Docking Connector entry. */
public final class DockingConnectorSalePointPonderPlugin implements PonderPlugin {
    private static final ResourceLocation DOCKING_CONNECTOR =
        ResourceLocation.fromNamespaceAndPath("simulated", "docking_connector");

    @Override
    public String getModId() {
        return "numiaerobridge";
    }

    @Override
    public void registerScenes(PonderSceneRegistrationHelper<ResourceLocation> helper) {
        helper.forComponents(DOCKING_CONNECTOR)
            .addStoryBoard("docking_connector/sale_point", DockingConnectorSalePointScenes::salePoint);
    }
}
