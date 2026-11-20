package dev.serhii.numiaerobridge;

import dev.serhii.numiaerobridge.ponder.DockingConnectorSalePointPonderPlugin;
import net.createmod.ponder.foundation.PonderIndex;
import net.neoforged.api.distmarker.Dist;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.fml.common.EventBusSubscriber;
import net.neoforged.fml.event.lifecycle.FMLClientSetupEvent;

/** Registers the addon tutorial in Create's client-side Ponder index. */
@EventBusSubscriber(
    modid = NumismaticsAeronauticsBridge.MOD_ID,
    bus = EventBusSubscriber.Bus.MOD,
    value = Dist.CLIENT
)
public final class NumismaticsAeronauticsBridgeClient {
    private NumismaticsAeronauticsBridgeClient() {
    }

    @SubscribeEvent
    public static void onClientSetup(FMLClientSetupEvent event) {
        event.enqueueWork(() -> PonderIndex.addPlugin(new DockingConnectorSalePointPonderPlugin()));
    }
}
