from pathlib import Path
import re

ROOT = Path(".")
BASE = ROOT / "src/main/java/com/example/taborganizer"

# 1) Persist merge groups by registry ID. The first selected tab is the visible master.
settings = BASE / "config/OrganizerSettings.java"
source = settings.read_text()

needle = '        if (data.tabNames == null) data.tabNames = new LinkedHashMap<>();'
if needle not in source:
    raise SystemExit("Could not locate tabNames initialization")
source = source.replace(
    needle,
    needle + '\n        if (data.tabMerges == null) data.tabMerges = new LinkedHashMap<>();',
    1
)

needle = '''    public static synchronized String getTabName(CreativeModeTab tab) {
        if (tab == null) return "";
        return data().tabNames.getOrDefault(getTabId(tab), "");
    }
'''
addition = needle + '''
    /** Returns the registry IDs whose contents are folded into this tab. */
    public static synchronized List<String> getMergedTabIds(CreativeModeTab master) {
        if (master == null) return new ArrayList<>();
        return new ArrayList<>(data().tabMerges.getOrDefault(getTabId(master), List.of()));
    }

    /** True when this tab's contents are displayed inside another tab. */
    public static synchronized boolean isMergedAway(CreativeModeTab tab) {
        if (tab == null) return false;
        String id = getTabId(tab);
        if (id.isBlank()) return false;
        for (Map.Entry<String, List<String>> entry : data().tabMerges.entrySet()) {
            if (!entry.getKey().equals(id) && entry.getValue() != null && entry.getValue().contains(id)) {
                return true;
            }
        }
        return false;
    }

    /**
     * Merge the selected tabs into the first one. Existing merge groups are flattened
     * so the resulting structure is always one master with a list of original source tabs.
     */
    public static synchronized void mergeTabs(List<CreativeModeTab> selectedTabs) {
        if (selectedTabs == null || selectedTabs.size() < 2) return;
        Data current = data();
        String masterId = getTabId(selectedTabs.get(0));
        if (masterId.isBlank()) return;

        java.util.LinkedHashSet<String> allIds = new java.util.LinkedHashSet<>();
        for (CreativeModeTab tab : selectedTabs) {
            String id = getTabId(tab);
            if (id.isBlank()) continue;
            allIds.add(id);
            List<String> oldMembers = current.tabMerges.remove(id);
            if (oldMembers != null) allIds.addAll(oldMembers);
        }
        allIds.add(masterId);
        allIds.remove(masterId);

        // Remove the newly grouped IDs from any older group, preventing overlapping groups.
        Map<String, List<String>> cleaned = new LinkedHashMap<>();
        for (Map.Entry<String, List<String>> entry : current.tabMerges.entrySet()) {
            if (entry.getKey().equals(masterId) || allIds.contains(entry.getKey())) continue;
            List<String> remaining = new ArrayList<>();
            if (entry.getValue() != null) {
                for (String id : entry.getValue()) {
                    if (!allIds.contains(id)) remaining.add(id);
                }
            }
            if (!remaining.isEmpty()) cleaned.put(entry.getKey(), remaining);
        }

        List<String> members = new ArrayList<>(allIds);
        members.remove(masterId);
        cleaned.put(masterId, members);
        current.tabMerges = cleaned;
        save();
    }

    /** Restore every original tab that was folded into the selected master. */
    public static synchronized int unmergeTab(CreativeModeTab master) {
        if (master == null) return 0;
        List<String> removed = data().tabMerges.remove(getTabId(master));
        save();
        return removed == null ? 0 : removed.size();
    }
'''
if needle not in source:
    raise SystemExit("Could not locate getTabName method")
source = source.replace(needle, addition, 1)

# getEditableTabs must never expose tabs whose contents are already folded into a master.
old = '            if (!isSpecialTab(tab) && tab.hasAnyItems()) result.add(tab);'
new = '            if (!isSpecialTab(tab) && !isMergedAway(tab) && tab.hasAnyItems()) result.add(tab);'
if old not in source:
    raise SystemExit("Could not locate editable-tab filter")
source = source.replace(old, new, 1)

# Keep the original tab IDs in the saved order so unmerging restores their position next to the master.
old = '''        for (CreativeModeTab tab : tabs) {
            String id = getTabId(tab);
            if (!id.isBlank()) current.tabOrder.add(id);
        }
'''
new = '''        for (CreativeModeTab tab : tabs) {
            String id = getTabId(tab);
            if (!id.isBlank() && !current.tabOrder.contains(id)) current.tabOrder.add(id);
            for (String mergedId : getMergedTabIds(tab)) {
                if (!mergedId.isBlank() && !current.tabOrder.contains(mergedId)) current.tabOrder.add(mergedId);
            }
        }
'''
if old not in source:
    raise SystemExit("Could not locate setLayout tab-order loop")
source = source.replace(old, new, 1)

needle = '        private Map<String, String> tabNames = new LinkedHashMap<>();'
if needle not in source:
    raise SystemExit("Could not locate tabNames data field")
source = source.replace(
    needle,
    needle + '\n        private Map<String, List<String>> tabMerges = new LinkedHashMap<>();',
    1
)
settings.write_text(source)

# 2) Remove folded source tabs from NeoForge's visible creative-tab sequence.
registry_mixin = BASE / "mixin/CreativeModeTabRegistryMixin.java"
source = registry_mixin.read_text()
needle = '''        for (CreativeModeTab tab : original) {
            if (OrganizerSettings.isSpecialTab(tab)) specialTabs.add(tab);
            else normalTabs.add(tab);
        }
'''
replacement = needle + '''
        normalTabs.removeIf(OrganizerSettings::isMergedAway);
'''
if needle not in source:
    raise SystemExit("Could not locate tab registry classification loop")
source = source.replace(needle, replacement, 1)
registry_mixin.write_text(source)

# 3) Aggregate the display items of source tabs into the master tab.
tab_mixin = BASE / "mixin/CreativeModeTabMixin.java"
tab_mixin.write_text(r'''package com.example.taborganizer.mixin;

import com.example.taborganizer.config.OrganizerSettings;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.item.CreativeModeTab;
import net.minecraft.world.item.ItemStack;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

import java.util.ArrayList;
import java.util.Collection;
import java.util.List;

@Mixin(value = CreativeModeTab.class, remap = false)
public abstract class CreativeModeTabMixin {
    @Inject(method = "getDisplayName", at = @At("RETURN"), cancellable = true, remap = false)
    private void taborganizer$applyTabAlias(CallbackInfoReturnable<Component> cir) {
        String alias = OrganizerSettings.getTabName((CreativeModeTab) (Object) this);
        if (!alias.isBlank()) {
            cir.setReturnValue(Component.literal(alias));
        }
    }

    @Inject(method = "getDisplayItems", at = @At("RETURN"), cancellable = true, remap = false)
    private void taborganizer$appendMergedTabItems(CallbackInfoReturnable<Collection<ItemStack>> cir) {
        CreativeModeTab master = (CreativeModeTab) (Object) this;
        List<String> mergedIds = OrganizerSettings.getMergedTabIds(master);
        if (mergedIds.isEmpty()) return;

        Collection<ItemStack> combined = new ArrayList<>(cir.getReturnValue());
        for (String id : mergedIds) {
            ResourceLocation key = ResourceLocation.tryParse(id);
            if (key == null) continue;
            CreativeModeTab source = BuiltInRegistries.CREATIVE_MODE_TAB.getOptional(key).orElse(null);
            if (source != null && source != master) {
                combined.addAll(source.getDisplayItems());
            }
        }
        cir.setReturnValue(combined);
    }
}
''')

# 4) Add Ctrl-click multi-selection, merge/unmerge buttons and visible selection markers.
screen = BASE / "client/gui/OrganizerScreen.java"
source = screen.read_text()

source = source.replace(
    'import java.util.ArrayList;\nimport java.util.List;',
    'import java.util.ArrayList;\nimport java.util.LinkedHashSet;\nimport java.util.List;\nimport java.util.Set;',
    1
)
source = source.replace(
    '    private static final int PANEL_HEIGHT = 312;',
    '    private static final int PANEL_HEIGHT = 360;',
    1
)
source = source.replace(
    '    private final List<CreativeModeTab> heapTabs = new ArrayList<>();',
    '    private final List<CreativeModeTab> heapTabs = new ArrayList<>();\n    private final Set<CreativeModeTab> mergeSelection = new LinkedHashSet<>();',
    1
)

source = source.replace(
    '        graphics.drawString(this.font, Component.translatable("screen.taborganizer.hint"),\n                x + 12, y + 25, 0xB8C0CC, false);',
    '        graphics.drawString(this.font, Component.literal("Ctrl+клік: вибери кілька вкладок для злиття"),\n                x + 12, y + 25, 0xB8C0CC, false);',
    1
)

# Move each existing action by locating its own button block, so new buttons
# cannot accidentally be shifted by a later replacement.
for marker, new_y in (
    ('Button.builder(Component.translatable("screen.taborganizer.reset")', 264),
    ('Button.builder(Component.translatable("screen.taborganizer.save")', 290),
    ('Button.builder(Component.translatable("gui.done")', 316),
):
    start_index = source.index(marker)
    bounds_index = source.index('.bounds(rightX, panelY + ', start_index)
    end_index = source.index(', rightWidth, 20).build());', bounds_index)
    source = source[:bounds_index] + f'.bounds(rightX, panelY + {new_y}' + source[end_index:]

needle = '''        this.addRenderableWidget(Button.builder(Component.translatable("screen.taborganizer.reset"), button -> {
'''
buttons = '''        this.addRenderableWidget(Button.builder(Component.literal("Об'єднати вибрані"), button -> mergeSelectedTabs())
                .bounds(rightX, panelY + 212, rightWidth, 20).build());

        this.addRenderableWidget(Button.builder(Component.literal("Роз'єднати вибрану"), button -> unmergeSelectedTab())
                .bounds(rightX, panelY + 238, rightWidth, 20).build());

''' + needle
if needle not in source:
    raise SystemExit("Could not locate reset button")
source = source.replace(needle, buttons, 1)

# Make sure reset also clears transient multi-selection.
source = source.replace(
    '            heapTabs.clear();\n            pageSizes = OrganizerSettings.getPageSizes(tabs.size());',
    '            heapTabs.clear();\n            mergeSelection.clear();\n            pageSizes = OrganizerSettings.getPageSizes(tabs.size());',
    1
)

# Ctrl-click toggles a tab in the merge selection and does not start a drag.
needle = '''                selectedIndex = entry.tabIndex;
                dragIndex = entry.tabIndex;
'''
replacement = '''                if (Screen.hasControlDown()) {
                    saveCurrentTabName();
                    selectedIndex = entry.tabIndex;
                    CreativeModeTab selectedTab = tabs.get(entry.tabIndex);
                    if (!mergeSelection.add(selectedTab)) mergeSelection.remove(selectedTab);
                    dragIndex = -1;
                    draggingHeap = false;
                    heapDragIndex = -1;
                    updatePageEditor(false);
                    return true;
                }

                mergeSelection.clear();
                saveCurrentTabName();
                selectedIndex = entry.tabIndex;
                dragIndex = entry.tabIndex;
'''
if needle not in source:
    raise SystemExit("Could not locate tab row click selection")
source = source.replace(needle, replacement, 1)

# Clicking a page header exits multi-select mode.
source = source.replace(
    '                if (entry.header) {\n                    saveCurrentPageTitle();',
    '                if (entry.header) {\n                    mergeSelection.clear();\n                    saveCurrentPageTitle();',
    1
)

# Render selected rows with a distinct highlight and a check marker.
old = '''                boolean selected = index == selectedIndex;
                boolean dragging = !draggingHeap && index == dragIndex;
                int background = dragging ? 0xFF6A5135 : (selected ? 0xFF465A73 : 0xFF252B33);
                graphics.fill(listX + 1, rowY + 1, listX + LIST_WIDTH - 1, rowY + ROW_HEIGHT - 1, background);
'''
new = '''                boolean selected = index == selectedIndex;
                boolean mergeSelected = mergeSelection.contains(tabs.get(index));
                boolean dragging = !draggingHeap && index == dragIndex;
                int background = dragging ? 0xFF6A5135
                        : (mergeSelected ? 0xFF5D5838 : (selected ? 0xFF465A73 : 0xFF252B33));
                graphics.fill(listX + 1, rowY + 1, listX + LIST_WIDTH - 1, rowY + ROW_HEIGHT - 1, background);
'''
if old not in source:
    raise SystemExit("Could not locate tab row rendering background")
source = source.replace(old, new, 1)

old = '''                graphics.drawString(this.font, trimToWidth(tab.getDisplayName().getString(), LIST_WIDTH - 42),
                        listX + 34, rowY + 5, 0xF2F2F2, false);
'''
new = '''                String rowLabel = tab.getDisplayName().getString();
                if (mergeSelected) rowLabel = "✓ " + rowLabel;
                graphics.drawString(this.font, trimToWidth(rowLabel, LIST_WIDTH - 42),
                        listX + 34, rowY + 5, 0xF2F2F2, false);
'''
if old not in source:
    raise SystemExit("Could not locate tab display label rendering")
source = source.replace(old, new, 1)

# Move the status line below the additional merge controls.
source = source.replace(
    'rightX, y + 290,',
    'rightX, y + 344,',
    1
)

# Add merge/unmerge actions before the list-entry helper.
needle = '    private static final class ListEntry {'
methods = '''    private void mergeSelectedTabs() {
        if (!heapTabs.isEmpty()) {
            setHeapReturnWarning();
            return;
        }
        if (mergeSelection.size() < 2) {
            statusMessage = "Затисни Ctrl і вибери щонайменше дві вкладки.";
            statusIsError = true;
            return;
        }

        saveCurrentPageTitle();
        saveCurrentTabName();
        List<CreativeModeTab> selectedTabs = new ArrayList<>(mergeSelection);
        CreativeModeTab master = selectedTabs.get(0);
        OrganizerSettings.mergeTabs(selectedTabs);

        tabs.clear();
        tabs.addAll(OrganizerSettings.getEditableTabs());
        pageSizes = OrganizerSettings.getPageSizes(tabs.size());
        selectedIndex = tabs.indexOf(master);
        if (selectedIndex < 0) selectedIndex = 0;
        mergeSelection.clear();
        scrollOffset = 0;
        OrganizerSettings.setLayout(tabs, pageSizes);
        updatePageEditor(true);
        ensureSelectionVisible();

        statusMessage = "Об'єднано вкладок: " + selectedTabs.size() + ". Основна: "
                + master.getDisplayName().getString();
        statusIsError = false;
    }

    private void unmergeSelectedTab() {
        if (!heapTabs.isEmpty()) {
            setHeapReturnWarning();
            return;
        }
        if (selectedIndex < 0 || selectedIndex >= tabs.size()) {
            statusMessage = "Спочатку вибери основну вкладку об'єднання.";
            statusIsError = true;
            return;
        }

        saveCurrentPageTitle();
        saveCurrentTabName();
        CreativeModeTab master = tabs.get(selectedIndex);
        int restored = OrganizerSettings.unmergeTab(master);
        if (restored == 0) {
            statusMessage = "Вибрана вкладка не містить об'єднаних вкладок.";
            statusIsError = true;
            return;
        }

        tabs.clear();
        tabs.addAll(OrganizerSettings.getEditableTabs());
        pageSizes = OrganizerSettings.getPageSizes(tabs.size());
        selectedIndex = Math.max(0, tabs.indexOf(master));
        mergeSelection.clear();
        OrganizerSettings.setLayout(tabs, pageSizes);
        updatePageEditor(true);
        ensureSelectionVisible();

        statusMessage = "Повернуто окремих вкладок: " + restored + ".";
        statusIsError = false;
    }

''' + needle
if needle not in source:
    raise SystemExit("Could not locate ListEntry helper for merge methods")
source = source.replace(needle, methods, 1)

screen.write_text(source)

# 5) Update the mod's internal version.
props = ROOT / "gradle.properties"
text = props.read_text()
text, count = re.subn(r"(?m)^mod_version=.*$", "mod_version=1.0.7", text, count=1)
if count != 1:
    raise SystemExit("Could not update gradle.properties to 1.0.7")
props.write_text(text)

toml = ROOT / "src/main/resources/META-INF/neoforge.mods.toml"
if toml.exists():
    text = toml.read_text()
    text = re.sub(r'(?m)^(version\s*=\s*")[^"]+(".*)$', r'\g<1>1.0.7\2', text)
    toml.write_text(text)

print("Applied beta 1.0.7: merge multiple creative tabs into one, keep source tabs hidden, and allow unmerging.")
