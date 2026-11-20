package dev.serhii.numiaerobridge;

import net.neoforged.fml.common.Mod;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@Mod(NumismaticsAeronauticsBridge.MOD_ID)
public final class NumismaticsAeronauticsBridge {
    public static final String MOD_ID = "numiaerobridge";
    public static final Logger LOGGER = LoggerFactory.getLogger("Numismatics Aeronautics Bridge");

    public NumismaticsAeronauticsBridge() {
        LOGGER.info("Numismatics Aeronautics Bridge loaded.");
    }
}
