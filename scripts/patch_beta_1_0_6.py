from pathlib import Path
import json
import re

ROOT = Path(".")
BASE = ROOT / "src/main/java/com/example/taborganizer"

# Store a separate display label for each creative tab by registry ID.
settings = BASE / "config/OrganizerSettings.java"
source = settings.read_text()

needle = '        if (data.pageNames == null) data.pageNames = new LinkedHashMap<>();'
if needle not in source:
    raise SystemExit("Could not locate pageNames initialization in OrganizerSettings")
source = source.replace(
    needle,
    needle + '\n        if (data.tabNames == null) data.tabNames = new LinkedHashMap<>();',
    1
)

needle = '''    public static synchronized String getPageName(int pageIndex) {
        if (pageIndex < 0) return "";
        return data().pageNames.getOrDefault(Integer.toString(pageIndex), "");
    }
'''
addition = needle + '''
    /** Save an independent display name for one creative tab. */
    public static synchronized void setTabName(CreativeModeTab tab, String title) {
        if (tab == null) return;
        String key = getTabId(tab);
        if (key.isBlank()) return;
        String cleanTitle = title == null ? "" : title.trim();
        if (cleanTitle.isEmpty()) data().tabNames.remove(key);
        else data().tabNames.put(key, cleanTitle);
    }

    public static synchronized String getTabName(CreativeModeTab tab) {
        if (tab == null) return "";
        return data().tabNames.getOrDefault(getTabId(tab), "");
    }
'''
if needle not in source:
    raise SystemExit("Could not locate getPageName in OrganizerSettings")
source = source.replace(needle, addition, 1)

needle = '        private Map<String, String> pageNames = new LinkedHashMap<>();'
if needle not in source:
    raise SystemExit("Could not locate pageNames data field")
source = source.replace(
    needle,
    needle + '\n        private Map<String, String> tabNames = new LinkedHashMap<>();',
    1
)
settings.write_text(source)

# Add a second, independent editor field for the selected tab's custom label.
screen = BASE / "client/gui/OrganizerScreen.java"
source = screen.read_text()

source = source.replace(
    '    private EditBox pageNameField;\n    private EditBox pageSizeField;',
    '    private EditBox pageNameField;\n    private EditBox pageSizeField;\n    private EditBox tabNameField;',
    1
)

old = '''        this.addRenderableWidget(pageSizeField);
        updatePageEditor(true);

        this.addRenderableWidget(Button.builder(Component.translatable("screen.taborganizer.apply_size"), button -> applyPageSize())
                .bounds(rightX + 52, panelY + 139, rightWidth - 52, 20).build());
'''
new = '''        this.addRenderableWidget(pageSizeField);

        tabNameField = new EditBox(this.font, rightX, panelY + 184, rightWidth, 20,
                Component.literal("Назва вкладки"));
        tabNameField.setMaxLength(48);
        this.addRenderableWidget(tabNameField);
        updatePageEditor(true);

        this.addRenderableWidget(Button.builder(Component.translatable("screen.taborganizer.apply_size"), button -> applyPageSize())
                .bounds(rightX + 52, panelY + 139, rightWidth - 52, 20).build());
'''
if old not in source:
    raise SystemExit("Could not locate size field setup")
source = source.replace(old, new, 1)

source = source.replace(
    '.bounds(rightX, panelY + 170, rightWidth, 20).build());',
    '.bounds(rightX, panelY + 212, rightWidth, 20).build());',
    1
)
source = source.replace(
    '.bounds(rightX, panelY + 198, rightWidth, 20).build());',
    '.bounds(rightX, panelY + 238, rightWidth, 20).build());',
    1
)
source = source.replace(
    '.bounds(rightX, panelY + 226, rightWidth, 20).build());',
    '.bounds(rightX, panelY + 264, rightWidth, 20).build());',
    1
)

# Persist the current tab alias before switching selection or closing.
needle = '''    private void saveCurrentPageTitle() {
        if (editingPageIndex >= 0 && pageNameField != null) {
            OrganizerSettings.setPageName(editingPageIndex, pageNameField.getValue());
        }
    }
'''
addition = needle + '''
    private void saveCurrentTabName() {
        if (selectedIndex >= 0 && selectedIndex < tabs.size() && tabNameField != null) {
            OrganizerSettings.setTabName(tabs.get(selectedIndex), tabNameField.getValue());
        }
    }
'''
if needle not in source:
    raise SystemExit("Could not locate saveCurrentPageTitle")
source = source.replace(needle, addition, 1)

old = '''    private void updatePageEditor(boolean force) {
        int newPage = pageIndexForSelection();
        if (newPage < 0) newPage = Math.max(0, Math.min(editingPageIndex, pageSizes.size() - 1));
        if (!force && newPage == editingPageIndex) return;

        saveCurrentPageTitle();
        editingPageIndex = newPage;
        if (pageNameField != null) {
            pageNameField.setValue(OrganizerSettings.getPageName(editingPageIndex));
        }
        if (pageSizeField != null) {
            int size = editingPageIndex >= 0 && editingPageIndex < pageSizes.size() ? pageSizes.get(editingPageIndex) : 0;
            pageSizeField.setValue(Integer.toString(size));
        }
    }
'''
new = '''    private void updatePageEditor(boolean force) {
        int newPage = pageIndexForSelection();
        if (newPage < 0) newPage = Math.max(0, Math.min(editingPageIndex, pageSizes.size() - 1));

        if (force || newPage != editingPageIndex) {
            saveCurrentPageTitle();
            editingPageIndex = newPage;
            if (pageNameField != null) {
                pageNameField.setValue(OrganizerSettings.getPageName(editingPageIndex));
            }
            if (pageSizeField != null) {
                int size = editingPageIndex >= 0 && editingPageIndex < pageSizes.size() ? pageSizes.get(editingPageIndex) : 0;
                pageSizeField.setValue(Integer.toString(size));
            }
        }

        if (tabNameField != null) {
            String tabName = selectedIndex >= 0 && selectedIndex < tabs.size()
                    ? OrganizerSettings.getTabName(tabs.get(selectedIndex)) : "";
            tabNameField.setValue(tabName);
        }
    }
'''
if old not in source:
    raise SystemExit("Could not replace updatePageEditor")
source = source.replace(old, new, 1)

# Save tab labels in the same places that save page names.
source = source.replace(
    '            saveCurrentPageTitle();\n            OrganizerSettings.resetOrder();',
    '            saveCurrentPageTitle();\n            saveCurrentTabName();\n            OrganizerSettings.resetOrder();',
    1
)
source = source.replace(
    '            saveCurrentPageTitle();\n            OrganizerSettings.setLayout(tabs, pageSizes);',
    '            saveCurrentPageTitle();\n            saveCurrentTabName();\n            OrganizerSettings.setLayout(tabs, pageSizes);',
    1
)
source = source.replace(
    '        saveCurrentPageTitle();\n        if (editingPageIndex < 0 || editingPageIndex >= pageSizes.size()) return;',
    '        saveCurrentPageTitle();\n        saveCurrentTabName();\n        if (editingPageIndex < 0 || editingPageIndex >= pageSizes.size()) return;',
    1
)
source = source.replace(
    '                    saveCurrentPageTitle();\n                    selectedIndex = Math.min(',
    '                    saveCurrentPageTitle();\n                    saveCurrentTabName();\n                    selectedIndex = Math.min(',
    1
)
source = source.replace(
    '                selectedIndex = entry.tabIndex;\n                dragIndex = entry.tabIndex;',
    '                saveCurrentTabName();\n                selectedIndex = entry.tabIndex;\n                dragIndex = entry.tabIndex;',
    1
)
source = source.replace(
    '        saveCurrentPageTitle();\n        CreativeModeTab moving = tabs.remove(sourceIndex);',
    '        saveCurrentPageTitle();\n        saveCurrentTabName();\n        CreativeModeTab moving = tabs.remove(sourceIndex);',
    1
)
source = source.replace(
    '        saveCurrentPageTitle();\n        OrganizerSettings.setLayout(tabs, pageSizes);',
    '        saveCurrentPageTitle();\n        saveCurrentTabName();\n        OrganizerSettings.setLayout(tabs, pageSizes);',
    1
)

# Display the separate tab-name prompt in the editor.
needle = '''        graphics.drawString(this.font, Component.translatable("screen.taborganizer.size_prompt"),
                rightX, y + 125, 0xE3E7ED, false);
'''
replacement = needle + '''        graphics.drawString(this.font, Component.literal("Назва вкладки (окремо від сторінки)"),
                rightX, y + 166, 0xE3E7ED, false);
'''
if needle not in source:
    raise SystemExit("Could not locate page size prompt")
source = source.replace(needle, replacement, 1)

# Move the status line lower so it does not overlap the new controls.
source = source.replace(
    'rightX, y + 260,',
    'rightX, y + 290,',
    1
)
screen.write_text(source)

# Add a client-side alias hook so the name appears on the actual creative tab as well.
tab_mixin = BASE / "mixin/CreativeModeTabMixin.java"
tab_mixin.write_text(r'''package com.example.taborganizer.mixin;

import com.example.taborganizer.config.OrganizerSettings;
import net.minecraft.network.chat.Component;
import net.minecraft.world.item.CreativeModeTab;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Mixin(value = CreativeModeTab.class, remap = false)
public abstract class CreativeModeTabMixin {
    @Inject(method = "getDisplayName", at = @At("RETURN"), cancellable = true, remap = false)
    private void taborganizer$applyTabAlias(CallbackInfoReturnable<Component> cir) {
        String alias = OrganizerSettings.getTabName((CreativeModeTab) (Object) this);
        if (!alias.isBlank()) {
            cir.setReturnValue(Component.literal(alias));
        }
    }
}
''')

# Register the mixin in the existing mixin configuration.
config_path = ROOT / "src/main/resources/taborganizer.mixins.json"
config = json.loads(config_path.read_text())
mixins = config.setdefault("mixins", [])
if "CreativeModeTabMixin" not in mixins:
    mixins.append("CreativeModeTabMixin")
config_path.write_text(json.dumps(config, indent=2) + "\n")

# Make the heading depend on the page currently selected in the creative inventory,
# not on the tab currently hovered by the mouse.
mixin = BASE / "mixin/CreativeModeInventoryScreenMixin.java"
source = mixin.read_text()
if "import net.neoforged.neoforge.client.gui.CreativeTabsScreenPage;" not in source:
    source = source.replace(
        "import net.minecraft.world.item.CreativeModeTab;",
        "import net.minecraft.world.item.CreativeModeTab;\nimport net.neoforged.neoforge.client.gui.CreativeTabsScreenPage;"
    )
if "import java.util.List;" not in source:
    source = source.replace("import java.util.ArrayList;", "import java.util.ArrayList;\nimport java.util.List;")

heading = r'''    @Inject(method = "renderLabels", at = @At("TAIL"), remap = false)
    private void taborganizer$renderPageHeading(GuiGraphics graphics, int mouseX, int mouseY, CallbackInfo ci) {
        CreativeModeInventoryScreen screen = (CreativeModeInventoryScreen) (Object) this;
        CreativeModeInventoryScreenAccessor accessor = (CreativeModeInventoryScreenAccessor) (Object) this;
        List<CreativeTabsScreenPage> pages = accessor.taborganizer$getPages();

        // Use the active page object, not selectedTab: Minecraft changes selectedTab
        // while hovering over tab icons, whereas currentPage changes only on page navigation.
        int pageIndex = pages.indexOf(screen.getCurrentPage());
        if (pageIndex < 0) return;

        String title = OrganizerSettings.getPageName(pageIndex);
        String label = "Сторінка " + (pageIndex + 1) + (title.isBlank() ? "" : ": " + title);

        var font = net.minecraft.client.Minecraft.getInstance().font;
        AbstractContainerScreenAccessor dimensions = (AbstractContainerScreenAccessor) (Object) this;
        int maxTextWidth = dimensions.taborganizer$getImageWidth() - 44;
        String visibleLabel = label;
        while (visibleLabel.length() > 1 && font.width(visibleLabel) > maxTextWidth) {
            visibleLabel = visibleLabel.substring(0, visibleLabel.length() - 1);
        }
        if (!visibleLabel.equals(label)) visibleLabel += "…";

        int boxWidth = font.width(visibleLabel) + 16;
        int boxX = (dimensions.taborganizer$getImageWidth() - boxWidth) / 2;
        int boxY = -70;

        graphics.fill(boxX, boxY, boxX + boxWidth, boxY + 20, 0xE623201A);
        graphics.renderOutline(boxX, boxY, boxWidth, 20, 0xFF98702C);
        graphics.drawString(font, Component.literal(visibleLabel), boxX + 8, boxY + 6, 0xFFFFD477, false);
    }
'''
pattern = re.compile(r'    @Inject\(method = "renderLabels".*?private void taborganizer\$renderPageHeading\(.*?\n    }\n', re.S)
source, count = pattern.subn(heading, source, count=1)
if count != 1:
    raise SystemExit("Could not replace page heading renderer with active-page logic")
mixin.write_text(source)

# Bump the internal mod version. The beta label is applied by the workflow artifact name.
props = ROOT / "gradle.properties"
text = props.read_text()
text, count = re.subn(r"(?m)^mod_version=.*$", "mod_version=1.0.6", text, count=1)
if count != 1:
    raise SystemExit("Could not update gradle.properties to 1.0.6")
props.write_text(text)

toml = ROOT / "src/main/resources/META-INF/neoforge.mods.toml"
if toml.exists():
    text = toml.read_text()
    text = re.sub(r'(?m)^(version\s*=\s*")[^"]+(".*)$', r'\g<1>1.0.6\2', text)
    toml.write_text(text)

print("Applied beta 1.0.6: persistent active-page heading, independent creative-tab aliases, and editor fields.")
