from pathlib import Path
import json
import re

ROOT = Path(".")
BASE = ROOT / "src/main/java/com/example/taborganizer"

# Resolve saved child registry IDs into CreativeModeTab instances for the editor tree.
settings = BASE / "config/OrganizerSettings.java"
source = settings.read_text()

if "import net.minecraft.resources.ResourceLocation;" not in source:
    source = source.replace(
        "import net.minecraft.core.registries.BuiltInRegistries;",
        "import net.minecraft.core.registries.BuiltInRegistries;\nimport net.minecraft.resources.ResourceLocation;"
    )

needle = '''    public static synchronized List<String> getMergedTabIds(CreativeModeTab master) {
        if (master == null) return new ArrayList<>();
        return new ArrayList<>(data().tabMerges.getOrDefault(getTabId(master), List.of()));
    }
'''
addition = needle + '''
    /** Resolve the tabs folded under a master tab, preserving the saved selection order. */
    public static synchronized List<CreativeModeTab> getMergedTabs(CreativeModeTab master) {
        List<CreativeModeTab> result = new ArrayList<>();
        for (String id : getMergedTabIds(master)) {
            ResourceLocation key = ResourceLocation.tryParse(id);
            if (key == null) continue;
            CreativeModeTab child = BuiltInRegistries.CREATIVE_MODE_TAB.getOptional(key).orElse(null);
            if (child != null && child != master) result.add(child);
        }
        return result;
    }

    /** The namespace is the mod ID, making it clear which mod owns each nested tab. */
    public static String getTabModLabel(CreativeModeTab tab) {
        String id = getTabId(tab);
        int separator = id.indexOf(':');
        String namespace = separator >= 0 ? id.substring(0, separator) : id;
        if (namespace.isBlank()) return "Unknown";
        return Character.toUpperCase(namespace.charAt(0)) + namespace.substring(1);
    }
'''
if needle not in source:
    raise SystemExit("Could not find getMergedTabIds in OrganizerSettings")
if "getMergedTabs(CreativeModeTab master)" not in source:
    source = source.replace(needle, addition, 1)
settings.write_text(source)

# Make merged tabs appear as indented child rows below their visible master in the editor.
screen = BASE / "client/gui/OrganizerScreen.java"
source = screen.read_text()

old = '''    private static final class ListEntry {
        private final boolean header;
        private final int pageIndex;
        private final int tabIndex;

        private ListEntry(boolean header, int pageIndex, int tabIndex) {
            this.header = header;
            this.pageIndex = pageIndex;
            this.tabIndex = tabIndex;
        }

        static ListEntry header(int pageIndex) { return new ListEntry(true, pageIndex, -1); }
        static ListEntry tab(int pageIndex, int tabIndex) { return new ListEntry(false, pageIndex, tabIndex); }
    }

    private List<ListEntry> buildListEntries() {
        List<ListEntry> entries = new ArrayList<>();
        int tabIndex = 0;
        for (int page = 0; page < pageSizes.size(); page++) {
            entries.add(ListEntry.header(page));
            for (int i = 0; i < pageSizes.get(page) && tabIndex < tabs.size(); i++) {
                entries.add(ListEntry.tab(page, tabIndex++));
            }
        }
        return entries;
    }
'''
new = '''    private static final class ListEntry {
        private final boolean header;
        private final boolean subgroup;
        private final int pageIndex;
        private final int tabIndex;
        private final CreativeModeTab childTab;

        private ListEntry(boolean header, boolean subgroup, int pageIndex, int tabIndex, CreativeModeTab childTab) {
            this.header = header;
            this.subgroup = subgroup;
            this.pageIndex = pageIndex;
            this.tabIndex = tabIndex;
            this.childTab = childTab;
        }

        static ListEntry header(int pageIndex) {
            return new ListEntry(true, false, pageIndex, -1, null);
        }

        static ListEntry tab(int pageIndex, int tabIndex) {
            return new ListEntry(false, false, pageIndex, tabIndex, null);
        }

        static ListEntry subgroup(int pageIndex, int parentTabIndex, CreativeModeTab childTab) {
            return new ListEntry(false, true, pageIndex, parentTabIndex, childTab);
        }
    }

    private List<ListEntry> buildListEntries() {
        List<ListEntry> entries = new ArrayList<>();
        int tabIndex = 0;
        for (int page = 0; page < pageSizes.size(); page++) {
            entries.add(ListEntry.header(page));
            for (int i = 0; i < pageSizes.get(page) && tabIndex < tabs.size(); i++) {
                int parentIndex = tabIndex++;
                CreativeModeTab master = tabs.get(parentIndex);
                entries.add(ListEntry.tab(page, parentIndex));
                for (CreativeModeTab child : OrganizerSettings.getMergedTabs(master)) {
                    entries.add(ListEntry.subgroup(page, parentIndex, child));
                }
            }
        }
        return entries;
    }
'''
if old not in source:
    raise SystemExit("Could not replace OrganizerScreen list entry model")
source = source.replace(old, new, 1)

old = '''            } else {
                int index = entry.tabIndex;
                boolean selected = index == selectedIndex;
                boolean mergeSelected = mergeSelection.contains(tabs.get(index));
                boolean dragging = !draggingHeap && index == dragIndex;
                int background = dragging ? 0xFF6A5135
                        : (mergeSelected ? 0xFF5D5838 : (selected ? 0xFF465A73 : 0xFF252B33));
                graphics.fill(listX + 1, rowY + 1, listX + LIST_WIDTH - 1, rowY + ROW_HEIGHT - 1, background);

                if (taborganizer$isDragging() && !dropToHeap && dropEntryIndex == entryIndex) {
                    int lineY = dropAfter ? rowY + ROW_HEIGHT - 2 : rowY + 1;
                    graphics.fill(listX + 2, lineY, listX + LIST_WIDTH - 2, lineY + 2, 0xFFFFD477);
                }

                CreativeModeTab tab = tabs.get(index);
                graphics.renderItem(tab.getIconItem(), listX + 11, rowY + 1);
                String rowLabel = tab.getDisplayName().getString();
                if (mergeSelected) rowLabel = "✓ " + rowLabel;
                graphics.drawString(this.font, trimToWidth(rowLabel, LIST_WIDTH - 42),
                        listX + 34, rowY + 5, 0xF2F2F2, false);
            }
'''
new = '''            } else if (entry.subgroup) {
                CreativeModeTab child = entry.childTab;
                graphics.fill(listX + 12, rowY + 1, listX + LIST_WIDTH - 1, rowY + ROW_HEIGHT - 1, 0xFF202A32);
                graphics.fill(listX + 14, rowY + 1, listX + 16, rowY + ROW_HEIGHT - 1, 0xFF98702C);
                graphics.drawString(this.font, "└", listX + 21, rowY + 5, 0xFFE7BE72, false);
                graphics.renderItem(child.getIconItem(), listX + 32, rowY + 1);
                String childLabel = OrganizerSettings.getTabModLabel(child) + " · " + child.getDisplayName().getString();
                graphics.drawString(this.font, trimToWidth(childLabel, LIST_WIDTH - 76),
                        listX + 55, rowY + 5, 0xFFBDC8D2, false);
            } else {
                int index = entry.tabIndex;
                boolean selected = index == selectedIndex;
                boolean mergeSelected = mergeSelection.contains(tabs.get(index));
                boolean dragging = !draggingHeap && index == dragIndex;
                int background = dragging ? 0xFF6A5135
                        : (mergeSelected ? 0xFF5D5838 : (selected ? 0xFF465A73 : 0xFF252B33));
                graphics.fill(listX + 1, rowY + 1, listX + LIST_WIDTH - 1, rowY + ROW_HEIGHT - 1, background);

                if (taborganizer$isDragging() && !dropToHeap && dropEntryIndex == entryIndex) {
                    int lineY = dropAfter ? rowY + ROW_HEIGHT - 2 : rowY + 1;
                    graphics.fill(listX + 2, lineY, listX + LIST_WIDTH - 2, lineY + 2, 0xFFFFD477);
                }

                CreativeModeTab tab = tabs.get(index);
                graphics.renderItem(tab.getIconItem(), listX + 11, rowY + 1);
                String rowLabel = tab.getDisplayName().getString();
                int mergedCount = OrganizerSettings.getMergedTabIds(tab).size();
                if (mergedCount > 0) rowLabel += "  (+" + mergedCount + ")";
                if (mergeSelected) rowLabel = "✓ " + rowLabel;
                graphics.drawString(this.font, trimToWidth(rowLabel, LIST_WIDTH - 42),
                        listX + 34, rowY + 5, 0xF2F2F2, false);
            }
'''
if old not in source:
    raise SystemExit("Could not replace OrganizerScreen row renderer")
source = source.replace(old, new, 1)

# Clicking a nested entry selects its master for the existing unmerge action without starting a drag.
needle = '''                if (entry.header) {
                    mergeSelection.clear();
                    saveCurrentPageTitle();
                    saveCurrentTabName();
                    selectedIndex = Math.min(OrganizerSettings.pageStart(pageSizes, entry.pageIndex), Math.max(0, tabs.size() - 1));
                    updatePageEditor(true);
                    return true;
                }
                saveCurrentTabName();
'''
replacement = '''                if (entry.header) {
                    mergeSelection.clear();
                    saveCurrentPageTitle();
                    saveCurrentTabName();
                    selectedIndex = Math.min(OrganizerSettings.pageStart(pageSizes, entry.pageIndex), Math.max(0, tabs.size() - 1));
                    updatePageEditor(true);
                    return true;
                }
                if (entry.subgroup) {
                    saveCurrentTabName();
                    selectedIndex = entry.tabIndex;
                    dragIndex = -1;
                    draggingHeap = false;
                    heapDragIndex = -1;
                    updatePageEditor(false);
                    statusMessage = "Група мода: " + OrganizerSettings.getTabModLabel(entry.childTab);
                    statusIsError = false;
                    return true;
                }
                saveCurrentTabName();
'''
if needle not in source:
    raise SystemExit("Could not add subgroup click behavior")
source = source.replace(needle, replacement, 1)

source = source.replace(
    'if (!entries.get(i).header && entries.get(i).tabIndex == selectedIndex) {',
    'if (!entries.get(i).header && !entries.get(i).subgroup && entries.get(i).tabIndex == selectedIndex) {',
    1
)

screen.write_text(source)

# Add a compact child-count indicator to the visible master tab label as well.
tab_mixin = BASE / "mixin/CreativeModeTabMixin.java"
source = tab_mixin.read_text()
old = '''    private void taborganizer$applyTabAlias(CallbackInfoReturnable<Component> cir) {
        String alias = OrganizerSettings.getTabName((CreativeModeTab) (Object) this);
        if (!alias.isBlank()) {
            cir.setReturnValue(Component.literal(alias));
        }
    }
'''
new = '''    private void taborganizer$applyTabAlias(CallbackInfoReturnable<Component> cir) {
        CreativeModeTab tab = (CreativeModeTab) (Object) this;
        String alias = OrganizerSettings.getTabName(tab);
        int mergedCount = OrganizerSettings.getMergedTabIds(tab).size();
        if (!alias.isBlank() || mergedCount > 0) {
            String displayName = alias.isBlank() ? cir.getReturnValue().getString() : alias;
            if (mergedCount > 0) displayName += " (+" + mergedCount + ")";
            cir.setReturnValue(Component.literal(displayName));
        }
    }
'''
if old not in source:
    raise SystemExit("Could not update merged tab label")
source = source.replace(old, new, 1)
tab_mixin.write_text(source)

# 3) Expose the creative inventory background height for the bottom page heading.
accessor = BASE / "mixin/accessor/AbstractContainerScreenAccessor.java"
source = accessor.read_text()
needle = '    int taborganizer$getImageWidth();'
replacement = needle + '\n\n    @Accessor(value = "imageHeight", remap = false)\n    int taborganizer$getImageHeight();'
if "taborganizer$getImageHeight" not in source:
    if needle not in source:
        raise SystemExit("Could not find imageWidth accessor")
    source = source.replace(needle, replacement, 1)
accessor.write_text(source)

# 4) Move the heading to the bottom over the page indicator and make the heading clickable.
mixin = BASE / "mixin/CreativeModeInventoryScreenMixin.java"
source = mixin.read_text()

imports = [
    ("import com.example.taborganizer.config.OrganizerSettings;",
     "import com.example.taborganizer.config.OrganizerSettings;\nimport com.example.taborganizer.client.gui.OrganizerScreen;"),
    ("import net.minecraft.client.gui.GuiGraphics;",
     "import net.minecraft.client.Minecraft;\nimport net.minecraft.client.gui.GuiGraphics;"),
    ("import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;",
     "import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;\nimport org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;")
]
for old_import, new_import in imports:
    if new_import not in source:
        if old_import not in source:
            raise SystemExit("Missing import insertion point: " + old_import)
        source = source.replace(old_import, new_import, 1)

source = source.replace(
    '        int boxWidth = font.width(visibleLabel) + 16;',
    '        int boxWidth = Math.max(76, font.width(visibleLabel) + 16);',
    1
)
source = source.replace(
    '        int boxY = -70;',
    '        int boxY = dimensions.taborganizer$getImageHeight() - 20;',
    1
)
source = source.replace(
    '        graphics.drawString(font, Component.literal(visibleLabel), boxX + 8, boxY + 6, 0xFFFFD477, false);',
    '        graphics.drawString(font, Component.literal(visibleLabel), boxX + (boxWidth - font.width(visibleLabel)) / 2, boxY + 6, 0xFFFFD477, false);',
    1
)

click_inject = r'''    @Inject(method = "mouseClicked", at = @At("HEAD"), cancellable = true, remap = false)
    private void taborganizer$openEditorFromPageHeading(double mouseX, double mouseY, int button,
            CallbackInfoReturnable<Boolean> cir) {
        if (button != 0) return;

        CreativeModeInventoryScreen screen = (CreativeModeInventoryScreen) (Object) this;
        CreativeModeInventoryScreenAccessor accessor = (CreativeModeInventoryScreenAccessor) (Object) this;
        List<CreativeTabsScreenPage> pages = accessor.taborganizer$getPages();
        int pageIndex = pages.indexOf(screen.getCurrentPage());
        if (pageIndex < 0) return;

        String title = OrganizerSettings.getPageName(pageIndex);
        String label = "Сторінка " + (pageIndex + 1) + (title.isBlank() ? "" : ": " + title);
        var font = Minecraft.getInstance().font;
        AbstractContainerScreenAccessor dimensions = (AbstractContainerScreenAccessor) (Object) this;

        int boxWidth = Math.max(76, font.width(label) + 16);
        int boxX = (dimensions.taborganizer$getImageWidth() - boxWidth) / 2;
        int boxY = dimensions.taborganizer$getImageHeight() - 20;
        double relativeMouseX = mouseX - dimensions.taborganizer$getLeftPos();
        double relativeMouseY = mouseY - dimensions.taborganizer$getTopPos();

        if (relativeMouseX >= boxX && relativeMouseX <= boxX + boxWidth
                && relativeMouseY >= boxY && relativeMouseY <= boxY + 20) {
            Minecraft.getInstance().setScreen(new OrganizerScreen(screen));
            cir.setReturnValue(true);
        }
    }
'''
if "taborganizer$openEditorFromPageHeading" not in source:
    pos = source.rfind("\n}")
    if pos < 0:
        raise SystemExit("Could not find class closing brace in inventory mixin")
    source = source[:pos] + "\n\n" + click_inject + source[pos:]
mixin.write_text(source)

# Bump the mod version to beta 1.0.8.
props = ROOT / "gradle.properties"
text = props.read_text()
text, count = re.subn(r"(?m)^mod_version=.*$", "mod_version=1.0.8", text, count=1)
if count != 1:
    raise SystemExit("Could not update gradle.properties to 1.0.8")
props.write_text(text)

toml = ROOT / "src/main/resources/META-INF/neoforge.mods.toml"
if toml.exists():
    text = toml.read_text()
    text = re.sub(r'(?m)^(version\s*=\s*")[^"]+(".*)$', r'\g<1>1.0.8\2', text)
    toml.write_text(text)

print("Applied beta 1.0.8: nested mod groups, clickable page heading, and bottom page label.")
