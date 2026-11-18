from pathlib import Path
import re

ROOT = Path(".")
BASE = ROOT / "src/main/java/com/example/taborganizer"

# ---------------------------------------------------------------------------
# 1) Restore the custom page title text.
#    The old scissor rectangle used negative local Y coordinates and clipped
#    the text away. Use a measured substring ticker instead, so no scissor is
#    needed and long titles remain inside the plaque.
# ---------------------------------------------------------------------------
mixin = BASE / "mixin/CreativeModeInventoryScreenMixin.java"
source = mixin.read_text()

start = source.find('        int textWidth = font.width(label);')
end = source.find('\n    }\n', start)
if start < 0 or end < 0:
    raise SystemExit("Could not locate the current page-title text rendering block")

render = r'''        int textWidth = font.width(label);
        String visibleLabel = label;
        int drawX;

        if (textWidth <= contentWidth) {
            drawX = contentX + (contentWidth - textWidth) / 2;
        } else {
            int overflow = textWidth - contentWidth;
            long dwellMillis = 1700L;
            long travelMillis = Math.max(3200L, overflow * 95L);
            long cycleMillis = dwellMillis * 2L + travelMillis * 2L;
            long phase = System.currentTimeMillis() % cycleMillis;

            float scroll;
            if (phase < dwellMillis) {
                scroll = 0.0F;
            } else if (phase < dwellMillis + travelMillis) {
                scroll = overflow * (float) (phase - dwellMillis) / travelMillis;
            } else if (phase < dwellMillis * 2L + travelMillis) {
                scroll = overflow;
            } else {
                long reversePhase = phase - (dwellMillis * 2L + travelMillis);
                scroll = overflow * (1.0F - (float) reversePhase / travelMillis);
            }

            // Advance the visible window by whole Unicode code points. Every
            // frame is measured, so the text never spills outside the plaque.
            int startIndex = 0;
            while (startIndex < label.length()) {
                int nextIndex = startIndex + Character.charCount(label.codePointAt(startIndex));
                if (font.width(label.substring(0, nextIndex)) > scroll) break;
                startIndex = nextIndex;
            }

            StringBuilder visible = new StringBuilder();
            for (int index = startIndex; index < label.length();) {
                int codePoint = label.codePointAt(index);
                String candidate = visible.toString() + new String(Character.toChars(codePoint));
                if (font.width(candidate) > contentWidth) break;
                visible.appendCodePoint(codePoint);
                index += Character.charCount(codePoint);
            }

            visibleLabel = visible.toString();
            drawX = contentX;
        }

        // Do not use enableScissor here: renderLabels uses the inventory's
        // translated pose, while a negative local-Y scissor clips the label.
        graphics.drawString(font, Component.literal(visibleLabel), drawX, boxY + 6, 0xFFFFD477, false);'''
source = source[:start] + render + source[end:]
mixin.write_text(source)

# ---------------------------------------------------------------------------
# 2) Rebuild the actual NeoForge CreativeTabsScreenPage list from saved sizes.
#    Previously only tab row/column coordinates were changed; NeoForge still
#    kept its own fixed batches of 10 tabs in CreativeModeInventoryScreen.pages.
# ---------------------------------------------------------------------------
accessor = BASE / "mixin/accessor/CreativeModeInventoryScreenAccessor.java"
source = accessor.read_text()
if "taborganizer$setPages" not in source:
    if "import org.spongepowered.asm.mixin.Mutable;" not in source:
        source = source.replace(
            "import org.spongepowered.asm.mixin.Mixin;",
            "import org.spongepowered.asm.mixin.Mixin;\nimport org.spongepowered.asm.mixin.Mutable;"
        )
    needle = '    @Accessor(value = "pages", remap = false)\n    List<CreativeTabsScreenPage> taborganizer$getPages();'
    replacement = needle + '''

    @Mutable
    @Accessor(value = "pages", remap = false)
    void taborganizer$setPages(List<CreativeTabsScreenPage> pages);'''
    if needle not in source:
        raise SystemExit("Could not find pages accessor in CreativeModeInventoryScreenAccessor")
    source = source.replace(needle, replacement, 1)
    accessor.write_text(source)

source = mixin.read_text()
if "taborganizer$applySavedPageSizes" not in source:
    inject = r'''    /**
     * Rebuild NeoForge's real page objects using the exact page sizes saved by
     * the organizer. Updating only CreativeModeTab.row/column is insufficient:
     * NeoForge otherwise keeps slicing the tabs into fixed groups of ten.
     */
    @Inject(method = "init", at = @At("TAIL"), remap = false)
    private void taborganizer$applySavedPageSizes(CallbackInfo ci) {
        CreativeModeInventoryScreen screen = (CreativeModeInventoryScreen) (Object) this;
        CreativeModeInventoryScreenAccessor screenAccessor =
                (CreativeModeInventoryScreenAccessor) (Object) this;

        List<CreativeModeTab> visibleTabs = OrganizerSettings.getEditableTabs();
        if (visibleTabs.isEmpty()) return;

        List<Integer> sizes = OrganizerSettings.getPageSizes(visibleTabs.size());
        if (sizes.isEmpty()) return;

        List<CreativeTabsScreenPage> oldPages = screenAccessor.taborganizer$getPages();
        int previousPage = oldPages.indexOf(screen.getCurrentPage());

        List<CreativeTabsScreenPage> rebuiltPages = new ArrayList<>();
        int start = 0;
        for (Integer requestedSize : sizes) {
            if (start >= visibleTabs.size()) break;
            int size = Math.max(1, Math.min(requestedSize, visibleTabs.size() - start));
            int end = start + size;
            rebuiltPages.add(new CreativeTabsScreenPage(
                    new ArrayList<>(visibleTabs.subList(start, end))));
            start = end;
        }

        // Defensive fallback in case an older or edited config has incomplete sizes.
        if (start < visibleTabs.size()) {
            rebuiltPages.add(new CreativeTabsScreenPage(
                    new ArrayList<>(visibleTabs.subList(start, visibleTabs.size()))));
        }
        if (rebuiltPages.isEmpty()) return;

        screenAccessor.taborganizer$setPages(rebuiltPages);

        CreativeModeTab selectedTab = CreativeModeInventoryScreenAccessor.taborganizer$getSelectedTab();
        int selectedIndex = visibleTabs.indexOf(selectedTab);
        int targetPage = selectedIndex >= 0
                ? OrganizerSettings.getPageIndexForTabIndex(selectedIndex, sizes)
                : Math.max(0, Math.min(previousPage, rebuiltPages.size() - 1));
        targetPage = Math.max(0, Math.min(targetPage, rebuiltPages.size() - 1));

        screen.setCurrentPage(rebuiltPages.get(targetPage));
    }
'''
    pos = source.rfind("\n}")
    if pos < 0:
        raise SystemExit("Could not find closing brace in CreativeModeInventoryScreenMixin")
    source = source[:pos] + "\n\n" + inject + source[pos:]
mixin.write_text(source)

# ---------------------------------------------------------------------------
# 3) Bump version metadata.
# ---------------------------------------------------------------------------
props = ROOT / "gradle.properties"
text = props.read_text()
text, count = re.subn(r"(?m)^mod_version=.*$", "mod_version=1.1.2", text, count=1)
if count != 1:
    raise SystemExit("Could not update gradle.properties to 1.1.2")
props.write_text(text)

toml = ROOT / "src/main/resources/META-INF/neoforge.mods.toml"
if toml.exists():
    text = toml.read_text()
    text = re.sub(r'(?m)^(version\s*=\s*")[^"]+(".*)$', r'\g<1>1.1.2\2', text)
    toml.write_text(text)

print("Applied beta 1.1.2: visible page-title ticker without scissor clipping and real NeoForge pages rebuilt from saved custom sizes.")
