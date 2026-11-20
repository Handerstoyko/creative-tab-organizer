package dev.serhii.numiaerobridge;

public interface DockingConnectorSalePointAccess {
    boolean numiaerobridge$isFluidMode();
    boolean numiaerobridge$toggleMode();
    boolean numiaerobridge$isSalePointControlled();
    Object numiaerobridge$getBoundState();
    Object numiaerobridge$getLocalSalePointState(boolean fluidMode);
    Object numiaerobridge$getActiveSalePointState(boolean fluidMode);
}
