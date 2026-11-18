from pathlib import Path
import re

ROOT = Path(".")
BASE = ROOT / "src/main/java/com/example/taborganizer"

# ---------------------------------------------------------------------------
# 1) Granular group controls: extract selected child tabs and reorder children.
# ---------------------------------------------------------------------------
settings = BASE / "config/OrganizerSettings.java"
source = settings.read_text()

needle = '''    /** Restore every original tab that was folded into the selected master. */
    public static synchronized int unmergeTab(CreativeModeTab master) {
        if (master == null) return 0;
        List<String> removed = data().tabMerges.remove(getTabId(master));
        save();
        return removed == null ? 0 : removed.size();
    }
'''
addition = needle + '''
    /** Remove only the requested children from a group; untouched children remain merged. */
    public static synchronized int removeMergedTabs(CreativeModeTab master, List<CreativeModeTab> children) {
        if (master == null || children == null || children.isEmpty()) return 0;
        String masterId = getTabId(master);
        List<String> current = data().tabMerges.get(masterId);
        if (current == null || current.isEmpty()) return 0;

        int removed = 0;
        for (CreativeModeTab child : children) {
            String childId = getTabId(child);
            if (!childId.isBlank() && current.remove(childId)) removed++;
        }

        if (current.isEmpty()) data().tabMerges.remove(masterId);
        save();
        return removed;
    }

    /** Move a child before or after another child in the same group. */
    public static synchronized boolean moveMergedTab(
            CreativeModeTab master, CreativeModeTab child, CreativeModeTab target, boolean after) {
        if (master == null || child == null || target == null || child == target) return false;

        List<String> current = data().tabMerges.get(getTabId(master));
        if (current == null) return false;

        String childId = getTabId(child);
        String targetId = getTabId(target);
        int from = current.indexOf(childId);
        int targetIndex = current.indexOf(targetId);
        if (from < 0 || targetIndex < 0) return false;

        String moving = current.remove(from);
        if (from < targetIndex) targetIndex--;
        int insertIndex = targetIndex + (after ? 1 : 0);
        insertIndex = Math.max(0, Math.min(current.size(), insertIndex));
        current.add(insertIndex, moving);
        save();
        return true;
    }

    /** Move one child up or down without changing the master tab. */
    public static synchronized boolean shiftMergedTab(CreativeModeTab master, CreativeModeTab child, int direction) {
        if (master == null || child == null || direction == 0) return false;
        List<String> current = data().tabMerges.get(getTabId(master));
        if (current == null) return false;

        int index = current.indexOf(getTabId(child));
        int target = index + Integer.signum(direction);
        if (index < 0 || target < 0 || target >= current.size()) return false;

        String moving = current.remove(index);
        current.add(target, moving);
        save();
        return true;
    }
'''
if needle not in source:
    raise SystemExit("Could not find unmergeTab in OrganizerSettings")
source = source.replace(needle, addition, 1)
settings.write_text(source)

# ---------------------------------------------------------------------------
# 2) Update the organizer: multi-select children, extract only selected ones,
#    drag-reorder child rows and provide up/down fallback controls.
# ---------------------------------------------------------------------------
screen = BASE / "client/gui/OrganizerScreen.java"
source = screen.read_text()

source = source.replace(
    '    private static final int PANEL_HEIGHT = 360;',
    '    private static final int PANEL_HEIGHT = 410;',
    1
)
source = source.replace(
    '    private final Set<CreativeModeTab> mergeSelection = new LinkedHashSet<>();',
    '    private final Set<CreativeModeTab> mergeSelection = new LinkedHashSet<>();\n'
    '    private final Set<CreativeModeTab> groupSelection = new LinkedHashSet<>();\n'
    '    private CreativeModeTab selectedGroupMaster;\n'
    '    private CreativeModeTab selectedGroupChild;',
    1
)
source = source.replace(
    '    private boolean draggingHeap;\n    private boolean dropToHeap;',
    '    private boolean draggingHeap;\n'
    '    private boolean draggingGroupChild;\n'
    '    private int groupDropTargetIndex = -1;\n'
    '    private boolean groupDropAfter;\n'
    '    private boolean dropToHeap;',
    1
)

# Keep page/tab editor field bound to a child when one is selected.
old = '''    private void saveCurrentTabName() {
        if (selectedIndex >= 0 && selectedIndex < tabs.size() && tabNameField != null) {
            OrganizerSettings.setTabName(tabs.get(selectedIndex), tabNameField.getValue());
        }
    }
'''
new = '''    private void saveCurrentTabName() {
        if (tabNameField == null) return;
        CreativeModeTab target = selectedGroupChild != null
                ? selectedGroupChild
                : (selectedIndex >= 0 && selectedIndex < tabs.size() ? tabs.get(selectedIndex) : null);
        if (target != null) OrganizerSettings.setTabName(target, tabNameField.getValue());
    }
'''
if old not in source:
    raise SystemExit("Could not replace saveCurrentTabName")
source = source.replace(old, new, 1)

old = '''        if (tabNameField != null) {
            String tabName = selectedIndex >= 0 && selectedIndex < tabs.size()
                    ? OrganizerSettings.getTabName(tabs.get(selectedIndex)) : "";
            tabNameField.setValue(tabName);
        }
'''
new = '''        if (tabNameField != null) {
            CreativeModeTab target = selectedGroupChild != null
                    ? selectedGroupChild
                    : (selectedIndex >= 0 && selectedIndex < tabs.size() ? tabs.get(selectedIndex) : null);
            tabNameField.setValue(target == null ? "" : OrganizerSettings.getTabName(target));
        }
'''
if old not in source:
    raise SystemExit("Could not replace tab-name field refresh")
source = source.replace(old, new, 1)

# Add group extraction and reorder actions to the right-hand control panel.
needle = '''        this.addRenderableWidget(Button.builder(Component.translatable("screen.taborganizer.reset"), button -> {
'''
buttons = '''        this.addRenderableWidget(Button.builder(Component.literal("Витягнути вибрані з групи"), button -> extractSelectedGroupTabs())
                .bounds(rightX, panelY + 264, rightWidth, 20).build());

        this.addRenderableWidget(Button.builder(Component.literal("↑ Угору"), button -> shiftSelectedGroupChild(-1))
                .bounds(rightX, panelY + 290, (rightWidth - 8) / 2, 20).build());

        this.addRenderableWidget(Button.builder(Component.literal("↓ Вниз"), button -> shiftSelectedGroupChild(1))
                .bounds(rightX + (rightWidth + 8) / 2, panelY + 290, (rightWidth - 8) / 2, 20).build());

''' + needle
if needle not in source:
    raise SystemExit("Could not find reset button for group controls")
source = source.replace(needle, buttons, 1)

# Shift existing lower controls down to make room.
for marker, new_y in (
    ('Button.builder(Component.translatable("screen.taborganizer.reset")', 316),
    ('Button.builder(Component.translatable("screen.taborganizer.save")', 342),
    ('Button.builder(Component.translatable("gui.done")', 368),
):
    start_index = source.index(marker)
    bounds_index = source.index('.bounds(rightX, panelY + ', start_index)
    end_index = source.index(', rightWidth, 20).build());', bounds_index)
    source = source[:bounds_index] + f'.bounds(rightX, panelY + {new_y}' + source[end_index:]

source = source.replace(
    'Component.literal("Ctrl+клік: вибери кілька вкладок для злиття")',
    'Component.literal("Ctrl+клік: вибирай вкладки або окремі елементи групи")',
    1
)

# Ensure reset clears transient group selection.
source = source.replace(
    '            mergeSelection.clear();\n            pageSizes = OrganizerSettings.getPageSizes(tabs.size());',
    '            mergeSelection.clear();\n            groupSelection.clear();\n            selectedGroupMaster = null;\n            selectedGroupChild = null;\n            pageSizes = OrganizerSettings.getPageSizes(tabs.size());',
    1
)

# Add methods for extraction and group reordering.
needle = '    private static final class ListEntry {'
methods = '''    private void refreshAfterGroupChange(CreativeModeTab master, String message) {
        tabs.clear();
        tabs.addAll(OrganizerSettings.getEditableTabs());
        pageSizes = OrganizerSettings.getPageSizes(tabs.size());
        selectedIndex = Math.max(0, tabs.indexOf(master));
        OrganizerSettings.setLayout(tabs, pageSizes);
        mergeSelection.clear();
        groupSelection.clear();
        selectedGroupChild = null;
        selectedGroupMaster = OrganizerSettings.getMergedTabIds(master).isEmpty() ? null : master;
        updatePageEditor(true);
        ensureSelectionVisible();
        statusMessage = message;
        statusIsError = false;
    }

    private void extractSelectedGroupTabs() {
        if (selectedGroupMaster == null || groupSelection.isEmpty()) {
            statusMessage = "Вибери одну або кілька вкладених вкладок (Ctrl+клік).";
            statusIsError = true;
            return;
        }

        saveCurrentPageTitle();
        saveCurrentTabName();
        List<CreativeModeTab> selectedChildren = new ArrayList<>(groupSelection);
        int removed = OrganizerSettings.removeMergedTabs(selectedGroupMaster, selectedChildren);
        if (removed <= 0) {
            statusMessage = "Не вдалося витягнути вибрані вкладки.";
            statusIsError = true;
            return;
        }
        refreshAfterGroupChange(selectedGroupMaster, "Витягнуто вкладок із групи: " + removed + ".");
    }

    private void shiftSelectedGroupChild(int direction) {
        if (selectedGroupMaster == null || selectedGroupChild == null || groupSelection.size() != 1) {
            statusMessage = "Вибери одну вкладену вкладку для зміни порядку.";
            statusIsError = true;
            return;
        }

        saveCurrentTabName();
        if (!OrganizerSettings.shiftMergedTab(selectedGroupMaster, selectedGroupChild, direction)) {
            statusMessage = direction < 0 ? "Це вже перша вкладка групи." : "Це вже остання вкладка групи.";
            statusIsError = true;
            return;
        }

        OrganizerSettings.setLayout(tabs, pageSizes);
        statusMessage = "Порядок вкладок усередині групи змінено.";
        statusIsError = false;
    }

    private void finishGroupChildDrag() {
        CreativeModeTab master = selectedGroupMaster;
        CreativeModeTab moving = selectedGroupChild;
        int targetIndex = groupDropTargetIndex;
        boolean after = groupDropAfter;
        draggingGroupChild = false;
        groupDropTargetIndex = -1;

        if (master == null || moving == null || targetIndex < 0) return;
        List<CreativeModeTab> children = OrganizerSettings.getMergedTabs(master);
        if (targetIndex >= children.size()) return;
        CreativeModeTab target = children.get(targetIndex);
        if (!OrganizerSettings.moveMergedTab(master, moving, target, after)) return;

        OrganizerSettings.setLayout(tabs, pageSizes);
        statusMessage = "Порядок вкладок усередині групи змінено.";
        statusIsError = false;
    }

''' + needle
if needle not in source:
    raise SystemExit("Could not find ListEntry insertion point")
source = source.replace(needle, methods, 1)

# Render nested group rows with independent highlighting and drag-drop insertion marker.
old = '''            } else if (entry.subgroup) {
                CreativeModeTab child = entry.childTab;
                graphics.fill(listX + 12, rowY + 1, listX + LIST_WIDTH - 1, rowY + ROW_HEIGHT - 1, 0xFF202A32);
                graphics.fill(listX + 14, rowY + 1, listX + 16, rowY + ROW_HEIGHT - 1, 0xFF98702C);
                graphics.drawString(this.font, "└", listX + 21, rowY + 5, 0xFFE7BE72, false);
                graphics.renderItem(child.getIconItem(), listX + 32, rowY + 1);
                String childLabel = OrganizerSettings.getTabModLabel(child) + " · " + child.getDisplayName().getString();
                graphics.drawString(this.font, trimToWidth(childLabel, LIST_WIDTH - 76),
                        listX + 55, rowY + 5, 0xFFBDC8D2, false);
'''
new = '''            } else if (entry.subgroup) {
                CreativeModeTab child = entry.childTab;
                boolean childSelected = groupSelection.contains(child);
                int childBg = draggingGroupChild && selectedGroupChild == child ? 0xFF6A5135
                        : (childSelected ? 0xFF574C35 : 0xFF202A32);
                graphics.fill(listX + 12, rowY + 1, listX + LIST_WIDTH - 1, rowY + ROW_HEIGHT - 1, childBg);
                graphics.fill(listX + 14, rowY + 1, listX + 16, rowY + ROW_HEIGHT - 1, 0xFF98702C);
                graphics.drawString(this.font, childSelected ? "✓" : "└", listX + 21, rowY + 5, 0xFFE7BE72, false);
                graphics.renderItem(child.getIconItem(), listX + 32, rowY + 1);
                String childLabel = OrganizerSettings.getTabModLabel(child) + " · " + child.getDisplayName().getString();
                graphics.drawString(this.font, trimToWidth(childLabel, LIST_WIDTH - 76),
                        listX + 55, rowY + 5, 0xFFBDC8D2, false);
                if (draggingGroupChild && selectedGroupMaster == tabs.get(entry.tabIndex)
                        && groupDropTargetIndex >= 0
                        && groupDropTargetIndex == OrganizerSettings.getMergedTabs(selectedGroupMaster).indexOf(child)) {
                    int markerY = groupDropAfter ? rowY + ROW_HEIGHT - 2 : rowY + 1;
                    graphics.fill(listX + 18, markerY, listX + LIST_WIDTH - 2, markerY + 2, 0xFFFFD477);
                }
'''
if old not in source:
    raise SystemExit("Could not replace subgroup row renderer")
source = source.replace(old, new, 1)

# Subgroup click: Ctrl-click toggles one child in the extraction selection.
# Plain click selects it and begins a drag within the same group.
old = '''                if (entry.subgroup) {
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
new = '''                if (entry.subgroup) {
                    saveCurrentTabName();
                    selectedIndex = entry.tabIndex;
                    CreativeModeTab clickedMaster = tabs.get(entry.tabIndex);
                    if (selectedGroupMaster != clickedMaster) groupSelection.clear();
                    selectedGroupMaster = clickedMaster;
                    selectedGroupChild = entry.childTab;

                    if (Screen.hasControlDown()) {
                        if (!groupSelection.add(entry.childTab)) groupSelection.remove(entry.childTab);
                        draggingGroupChild = false;
                        groupDropTargetIndex = -1;
                        dragIndex = -1;
                    } else {
                        groupSelection.clear();
                        groupSelection.add(entry.childTab);
                        draggingGroupChild = true;
                        groupDropTargetIndex = -1;
                        dragIndex = -1;
                    }

                    draggingHeap = false;
                    heapDragIndex = -1;
                    updatePageEditor(false);
                    statusMessage = "Група " + OrganizerSettings.getTabModLabel(entry.childTab)
                            + ". Ctrl+клік додає вкладку до вибірки.";
                    statusIsError = false;
                    return true;
                }
                saveCurrentTabName();
                groupSelection.clear();
                selectedGroupMaster = null;
                selectedGroupChild = null;
                draggingGroupChild = false;
'''
if old not in source:
    raise SystemExit("Could not replace subgroup click handler")
source = source.replace(old, new, 1)

# Header selection exits both merge and nested-group selection modes.
source = source.replace(
    '                    mergeSelection.clear();\n                    saveCurrentPageTitle();',
    '                    mergeSelection.clear();\n                    groupSelection.clear();\n                    selectedGroupMaster = null;\n                    selectedGroupChild = null;\n                    draggingGroupChild = false;\n                    saveCurrentPageTitle();',
    1
)

# Include group dragging in the shared drag indicator.
source = source.replace(
    '        return dragIndex >= 0 || draggingHeap;',
    '        return dragIndex >= 0 || draggingHeap || draggingGroupChild;',
    1
)

# Complete a nested-tab drag before the main-tab drag path.
source = source.replace(
    '''    public boolean mouseDragged(double mouseX, double mouseY, int button, double dragX, double dragY) {
        mouseX /= uiScale;
        mouseY /= uiScale;
        dragX /= uiScale;
        dragY /= uiScale;
''',
    '''    public boolean mouseDragged(double mouseX, double mouseY, int button, double dragX, double dragY) {
        mouseX /= uiScale;
        mouseY /= uiScale;
        dragX /= uiScale;
        dragY /= uiScale;

        if (button == 0 && draggingGroupChild) {
            groupDropTargetIndex = -1;
            if (isInsideTabList(mouseX, mouseY)) {
                int entryIndex = rowIndexAt(mouseY);
                List<ListEntry> entries = buildListEntries();
                if (entryIndex >= 0 && entryIndex < entries.size()) {
                    ListEntry entry = entries.get(entryIndex);
                    if (entry.subgroup && entry.tabIndex >= 0 && entry.tabIndex < tabs.size()
                            && tabs.get(entry.tabIndex) == selectedGroupMaster
                            && entry.childTab != selectedGroupChild) {
                        groupDropTargetIndex = OrganizerSettings.getMergedTabs(selectedGroupMaster).indexOf(entry.childTab);
                        double rowY = listTop() + (entryIndex - scrollOffset) * ROW_HEIGHT;
                        groupDropAfter = mouseY >= rowY + ROW_HEIGHT / 2.0;
                    }
                }
            }
            return true;
        }
'''
)
source = source.replace(
    '''    public boolean mouseReleased(double mouseX, double mouseY, int button) {
        if (button == 0 && taborganizer$isDragging()) {
            finishDrag();
            return true;
        }
''',
    '''    public boolean mouseReleased(double mouseX, double mouseY, int button) {
        if (button == 0 && draggingGroupChild) {
            finishGroupChildDrag();
            return true;
        }
        if (button == 0 && taborganizer$isDragging()) {
            finishDrag();
            return true;
        }
'''
)
source = source.replace(
    '''        draggingHeap = false;
        dropToHeap = false;
''',
    '''        draggingHeap = false;
        draggingGroupChild = false;
        groupDropTargetIndex = -1;
        dropToHeap = false;
''',
    1
)

# Place the status text below the additional group controls.
source = source.replace('rightX, y + 344,', 'rightX, y + 392,', 1)

screen.write_text(source)

# ---------------------------------------------------------------------------
# 3) Place the page-name plaque exactly between the page arrows, covering the
#    vanilla "1 / N" indicator. Long titles scroll slowly and pause at both ends.
# ---------------------------------------------------------------------------
mixin = BASE / "mixin/CreativeModeInventoryScreenMixin.java"
source = mixin.read_text()

# Replace the previous renderLabels hook; render() runs after the vanilla counter.
heading = r'''    @Inject(method = "render", at = @At("TAIL"), remap = false)
    private void taborganizer$renderPageHeading(GuiGraphics graphics, int mouseX, int mouseY,
            float partialTick, CallbackInfo ci) {
        CreativeModeInventoryScreen screen = (CreativeModeInventoryScreen) (Object) this;
        CreativeModeInventoryScreenAccessor accessor = (CreativeModeInventoryScreenAccessor) (Object) this;
        List<CreativeTabsScreenPage> pages = accessor.taborganizer$getPages();

        int pageIndex = pages.indexOf(screen.getCurrentPage());
        if (pageIndex < 0) return;

        String title = OrganizerSettings.getPageName(pageIndex);
        String label = "Сторінка " + (pageIndex + 1) + (title.isBlank() ? "" : ": " + title);

        var font = Minecraft.getInstance().font;
        AbstractContainerScreenAccessor dimensions = (AbstractContainerScreenAccessor) (Object) this;

        // Page arrows occupy [leftPos, leftPos+20] and the mirrored right edge.
        // Four pixels of breathing room keep the plaque and its text off both buttons.
        int boxX = dimensions.taborganizer$getLeftPos() + 24;
        int boxY = dimensions.taborganizer$getTopPos() - 50;
        int boxWidth = Math.max(40, dimensions.taborganizer$getImageWidth() - 48);
        int boxHeight = 20;
        int contentX = boxX + 8;
        int contentWidth = boxWidth - 16;

        // Fully opaque fill masks the vanilla page counter underneath this plaque.
        graphics.fill(boxX, boxY, boxX + boxWidth, boxY + boxHeight, 0xFF202329);
        graphics.renderOutline(boxX, boxY, boxWidth, boxHeight, 0xFF98702C);

        int textWidth = font.width(label);
        int drawX;
        if (textWidth <= contentWidth) {
            drawX = contentX + (contentWidth - textWidth) / 2;
        } else {
            int overflow = textWidth - contentWidth;
            long dwellMillis = 1600L;
            long travelMillis = Math.max(1800L, overflow * 55L);
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
            drawX = contentX - Math.round(scroll);
        }

        graphics.enableScissor(contentX, boxY + 2, contentX + contentWidth, boxY + boxHeight - 2);
        graphics.drawString(font, Component.literal(label), drawX, boxY + 6, 0xFFFFD477, false);
        graphics.disableScissor();
    }
'''
pattern = re.compile(
    r'    @Inject\(method = "renderLabels".*?private void taborganizer\$renderPageHeading\(.*?\n    }\n',
    re.S
)
source, count = pattern.subn(heading, source, count=1)
if count != 1:
    raise SystemExit("Could not replace old page heading hook with navigation-bar renderer")

# Update the click hitbox to match the plaque between the arrows.
click_pattern = re.compile(
    r'    @Inject\(method = "mouseClicked".*?private void taborganizer\$openEditorFromPageHeading\(.*?\n    }\n',
    re.S
)
click = r'''    @Inject(method = "mouseClicked", at = @At("HEAD"), cancellable = true, remap = false)
    private void taborganizer$openEditorFromPageHeading(double mouseX, double mouseY, int button,
            CallbackInfoReturnable<Boolean> cir) {
        if (button != 0) return;

        CreativeModeInventoryScreen screen = (CreativeModeInventoryScreen) (Object) this;
        CreativeModeInventoryScreenAccessor accessor = (CreativeModeInventoryScreenAccessor) (Object) this;
        List<CreativeTabsScreenPage> pages = accessor.taborganizer$getPages();
        int pageIndex = pages.indexOf(screen.getCurrentPage());
        if (pageIndex < 0) return;

        AbstractContainerScreenAccessor dimensions = (AbstractContainerScreenAccessor) (Object) this;
        int boxX = dimensions.taborganizer$getLeftPos() + 24;
        int boxY = dimensions.taborganizer$getTopPos() - 50;
        int boxWidth = Math.max(40, dimensions.taborganizer$getImageWidth() - 48);

        if (mouseX >= boxX && mouseX <= boxX + boxWidth
                && mouseY >= boxY && mouseY <= boxY + 20) {
            Minecraft.getInstance().setScreen(new OrganizerScreen(screen));
            cir.setReturnValue(true);
        }
    }
'''
source, count = click_pattern.subn(click, source, count=1)
if count != 1:
    raise SystemExit("Could not replace page-heading click hitbox")
mixin.write_text(source)

# ---------------------------------------------------------------------------
# 4) Bump the version.
# ---------------------------------------------------------------------------
props = ROOT / "gradle.properties"
text = props.read_text()
text, count = re.subn(r"(?m)^mod_version=.*$", "mod_version=1.0.9", text, count=1)
if count != 1:
    raise SystemExit("Could not update gradle.properties to 1.0.9")
props.write_text(text)

toml = ROOT / "src/main/resources/META-INF/neoforge.mods.toml"
if toml.exists():
    text = toml.read_text()
    text = re.sub(r'(?m)^(version\s*=\s*")[^"]+(".*)$', r'\g<1>1.0.9\2', text)
    toml.write_text(text)

print("Applied beta 1.0.9: page-title plaque replaces the vanilla counter between arrows, long labels scroll slowly, and nested group children can be extracted/reordered individually.")
