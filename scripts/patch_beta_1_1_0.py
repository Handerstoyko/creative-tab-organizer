from pathlib import Path
import re

ROOT = Path(".")
BASE = ROOT / "src/main/java/com/example/taborganizer"

# ---------------------------------------------------------------------------
# 1) Group data helpers: create empty groups, add top-level tabs, transfer
#    children between groups, and flatten a group's children when moving it.
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
if needle not in source:
    raise SystemExit("Could not locate unmergeTab in OrganizerSettings")

if "createTabGroup(CreativeModeTab master)" not in source:
    methods = '''    /** Create an empty group anchored to a visible creative tab. */
    public static synchronized boolean createTabGroup(CreativeModeTab master) {
        if (master == null) return false;
        String masterId = getTabId(master);
        if (masterId.isBlank()) return false;
        if (!data().tabMerges.containsKey(masterId)) {
            data().tabMerges.put(masterId, new ArrayList<>());
            save();
        }
        return true;
    }

    /** True if this visible tab is already acting as a group container. */
    public static synchronized boolean isTabGroup(CreativeModeTab master) {
        if (master == null) return false;
        return data().tabMerges.containsKey(getTabId(master));
    }

    /**
     * Add a visible tab to a target group. If the moved tab itself owns a group,
     * its children are flattened into the destination so groups remain one level deep.
     */
    public static synchronized boolean addTabToGroup(CreativeModeTab master, CreativeModeTab child) {
        if (master == null || child == null || master == child) return false;
        String masterId = getTabId(master);
        String childId = getTabId(child);
        if (masterId.isBlank() || childId.isBlank() || masterId.equals(childId)) return false;

        Data current = data();
        List<String> destination = current.tabMerges.computeIfAbsent(masterId, key -> new ArrayList<>());
        if (destination.contains(childId)) return false;

        // Detach this tab from any previous group before attaching it to the new one.
        for (Map.Entry<String, List<String>> entry : current.tabMerges.entrySet()) {
            if (entry.getKey().equals(masterId) || entry.getValue() == null) continue;
            entry.getValue().remove(childId);
        }

        destination.add(childId);

        // Move any nested children with their former master and flatten the hierarchy.
        List<String> formerChildren = current.tabMerges.remove(childId);
        if (formerChildren != null) {
            for (String formerChildId : formerChildren) {
                if (!formerChildId.equals(masterId) && !destination.contains(formerChildId)) {
                    destination.add(formerChildId);
                }
            }
        }

        // Keep empty groups available as future drag-and-drop targets.
        save();
        return true;
    }

    /** Move one existing child from its current group into a different group. */
    public static synchronized boolean moveMergedTabToGroup(
            CreativeModeTab sourceMaster, CreativeModeTab child, CreativeModeTab targetMaster) {
        if (sourceMaster == null || child == null || targetMaster == null
                || sourceMaster == targetMaster || child == targetMaster) return false;

        List<String> source = data().tabMerges.get(getTabId(sourceMaster));
        if (source == null || !source.remove(getTabId(child))) return false;

        // Keep the source group as a valid, empty group if its last child was moved out.
        data().tabMerges.putIfAbsent(getTabId(sourceMaster), source);
        boolean added = addTabToGroup(targetMaster, child);
        if (!added) {
            source.add(getTabId(child));
            save();
            return false;
        }
        save();
        return true;
    }

'''
    source = source.replace(needle, methods + needle, 1)
settings.write_text(source)

settings.write_text(source)

# ---------------------------------------------------------------------------
# 2) Simplify the editor: remove the merge/unmerge/extract/up/down buttons.
#    Sorting and grouping will be performed directly in the tab list.
# ---------------------------------------------------------------------------
screen = BASE / "client/gui/OrganizerScreen.java"
source = screen.read_text()

source = source.replace(
    '    private static final int PANEL_HEIGHT = 410;',
    '    private static final int PANEL_HEIGHT = 312;',
    1
)

# Remove the controls that are now replaced by drag-and-drop.
button_blocks = [
'''        this.addRenderableWidget(Button.builder(Component.literal("Об'єднати вибрані"), button -> mergeSelectedTabs())
                .bounds(rightX, panelY + 212, rightWidth, 20).build());

''',
'''        this.addRenderableWidget(Button.builder(Component.literal("Роз'єднати вибрану"), button -> unmergeSelectedTab())
                .bounds(rightX, panelY + 238, rightWidth, 20).build());

''',
'''        this.addRenderableWidget(Button.builder(Component.literal("Витягнути вибрані з групи"), button -> extractSelectedGroupTabs())
                .bounds(rightX, panelY + 264, rightWidth, 20).build());

''',
'''        this.addRenderableWidget(Button.builder(Component.literal("↑ Угору"), button -> shiftSelectedGroupChild(-1))
                .bounds(rightX, panelY + 290, (rightWidth - 8) / 2, 20).build());

''',
'''        this.addRenderableWidget(Button.builder(Component.literal("↓ Вниз"), button -> shiftSelectedGroupChild(1))
                .bounds(rightX + (rightWidth + 8) / 2, panelY + 290, (rightWidth - 8) / 2, 20).build());

'''
]
for block in button_blocks:
    if block not in source:
        raise SystemExit("Could not find an old group action button block to remove")
    source = source.replace(block, "", 1)

# Reposition the remaining simple controls into a compact stack.
for marker, new_y in (
    ('Button.builder(Component.translatable("screen.taborganizer.reset")', 212),
    ('Button.builder(Component.translatable("screen.taborganizer.save")', 238),
    ('Button.builder(Component.translatable("gui.done")', 264),
):
    start_index = source.index(marker)
    bounds_index = source.index('.bounds(rightX, panelY + ', start_index)
    end_index = source.index(', rightWidth, 20).build());', bounds_index)
    source = source[:bounds_index] + f'.bounds(rightX, panelY + {new_y}' + source[end_index:]

source = source.replace('rightX, y + 392,', 'rightX, y + 290,', 1)

# Remove the old Ctrl-click multi-select flow for creating merged tabs.
old_ctrl = '''                if (Screen.hasControlDown()) {
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
'''
if old_ctrl in source:
    source = source.replace(old_ctrl, '''                mergeSelection.clear();
                saveCurrentTabName();
''', 1)

# Make Ctrl-click on a nested child behave like a normal select-and-drag.
old_child_select = '''                    if (Screen.hasControlDown()) {
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
'''
new_child_select = '''                    groupSelection.clear();
                    groupSelection.add(entry.childTab);
                    draggingGroupChild = true;
                    groupDropTargetIndex = -1;
                    groupDropTargetMaster = null;
                    dragIndex = -1;
'''
if old_child_select not in source:
    raise SystemExit("Could not simplify nested-child selection")
source = source.replace(old_child_select, new_child_select, 1)

# Track the destination master when moving a child from one group to another.
if 'private CreativeModeTab groupDropTargetMaster;' not in source:
    source = source.replace(
        '    private int groupDropTargetIndex = -1;\n',
        '    private int groupDropTargetIndex = -1;\n    private CreativeModeTab groupDropTargetMaster;\n',
        1
    )

# Add the small [+] group action at the right edge of the selected main-tab row.
old_render = '''                String rowLabel = tab.getDisplayName().getString();
                int mergedCount = OrganizerSettings.getMergedTabIds(tab).size();
                if (mergedCount > 0) rowLabel += "  (+" + mergedCount + ")";
                if (mergeSelected) rowLabel = "✓ " + rowLabel;
                graphics.drawString(this.font, trimToWidth(rowLabel, LIST_WIDTH - 42),
                        listX + 34, rowY + 5, 0xF2F2F2, false);
'''
new_render = '''                String rowLabel = tab.getDisplayName().getString();
                int mergedCount = OrganizerSettings.getMergedTabIds(tab).size();
                if (mergedCount > 0) rowLabel += "  (+" + mergedCount + ")";
                if (mergeSelected) rowLabel = "✓ " + rowLabel;
                graphics.drawString(this.font, trimToWidth(rowLabel, LIST_WIDTH - 66),
                        listX + 34, rowY + 5, 0xF2F2F2, false);

                int groupButtonX = listX + LIST_WIDTH - 21;
                int groupButtonY = rowY + 2;
                boolean isGroup = OrganizerSettings.isTabGroup(tab);
                boolean groupButtonHovered = scaledMouseX >= groupButtonX && scaledMouseX < groupButtonX + 17
                        && scaledMouseY >= groupButtonY && scaledMouseY < groupButtonY + 14;
                if (index == selectedIndex || isGroup) {
                    graphics.fill(groupButtonX, groupButtonY, groupButtonX + 17, groupButtonY + 14,
                            isGroup ? 0xFF6C5736 : 0xFF394754);
                    graphics.renderOutline(groupButtonX, groupButtonY, 17, 14, 0xFF98702C);
                    graphics.drawString(this.font, isGroup ? "G" : "+", groupButtonX + 5, groupButtonY + 3,
                            0xFFFFD477, false);
                    if (groupButtonHovered) {
                        groupButtonTooltip = isGroup
                                ? "Група готова — перетягни вкладки сюди"
                                : "Створити групу";
                    }
                }

                if (dragIndex >= 0 && isGroup && dropTabIndex == index && !dropToHeap) {
                    graphics.renderOutline(listX + 1, rowY + 1, LIST_WIDTH - 2, ROW_HEIGHT - 2, 0xFFFFD477);
                }
                if (draggingGroupChild && groupDropTargetMaster == tab) {
                    graphics.renderOutline(listX + 1, rowY + 1, LIST_WIDTH - 2, ROW_HEIGHT - 2, 0xFFFFD477);
                }
'''
if old_render not in source:
    raise SystemExit("Could not locate main tab row renderer for group plus icon")
source = source.replace(old_render, new_render, 1)

# Add a tooltip variable near the start of render and display it above the list.
render_anchor = '''        int x = panelX;
        int y = panelY;
'''
if render_anchor not in source:
    raise SystemExit("Could not locate OrganizerScreen render start")
source = source.replace(
    render_anchor,
    render_anchor + '        String groupButtonTooltip = null;\n',
    1
)

# Render tooltip after widgets so it stays above the editor controls.
source = source.replace(
    '''        super.render(graphics, scaledMouseX, scaledMouseY, partialTick);
        graphics.pose().popPose();
''',
    '''        super.render(graphics, scaledMouseX, scaledMouseY, partialTick);
        if (groupButtonTooltip != null) {
            graphics.renderTooltip(this.font, Component.literal(groupButtonTooltip), scaledMouseX, scaledMouseY);
        }
        graphics.pose().popPose();
''',
    1
)

# Clicking [+] creates an empty group anchored to that tab. The group stays visible
# and can receive other tabs by dragging them onto its row.
needle = '''                if (entry.subgroup) {
                    saveCurrentTabName();
'''
insert = '''                if (!entry.subgroup && mouseX >= panelX + LIST_X_OFFSET + LIST_WIDTH - 22) {
                    saveCurrentPageTitle();
                    saveCurrentTabName();
                    selectedIndex = entry.tabIndex;
                    CreativeModeTab groupMaster = tabs.get(entry.tabIndex);
                    if (OrganizerSettings.createTabGroup(groupMaster)) {
                        statusMessage = "Групу створено. Перетягни потрібні вкладки на цей рядок.";
                        statusIsError = false;
                    } else {
                        statusMessage = "Не вдалося створити групу для цієї вкладки.";
                        statusIsError = true;
                    }
                    updatePageEditor(true);
                    return true;
                }

''' + needle
if needle not in source:
    raise SystemExit("Could not locate subgroup mouse-click branch for plus action")
source = source.replace(needle, insert, 1)

# Dragging a subgroup child may target either another child in its current group
# (reorder) or a different group master (transfer).
old_drag = '''        if (button == 0 && draggingGroupChild) {
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
new_drag = '''        if (button == 0 && draggingGroupChild) {
            groupDropTargetIndex = -1;
            groupDropTargetMaster = null;
            if (isInsideTabList(mouseX, mouseY)) {
                int entryIndex = rowIndexAt(mouseY);
                List<ListEntry> entries = buildListEntries();
                if (entryIndex >= 0 && entryIndex < entries.size()) {
                    ListEntry entry = entries.get(entryIndex);
                    if (entry.subgroup && entry.tabIndex >= 0 && entry.tabIndex < tabs.size()) {
                        CreativeModeTab rowMaster = tabs.get(entry.tabIndex);
                        if (rowMaster == selectedGroupMaster && entry.childTab != selectedGroupChild) {
                            groupDropTargetIndex = OrganizerSettings.getMergedTabs(selectedGroupMaster).indexOf(entry.childTab);
                            double rowY = listTop() + (entryIndex - scrollOffset) * ROW_HEIGHT;
                            groupDropAfter = mouseY >= rowY + ROW_HEIGHT / 2.0;
                        } else if (rowMaster != selectedGroupMaster && OrganizerSettings.isTabGroup(rowMaster)) {
                            groupDropTargetMaster = rowMaster;
                        }
                    } else if (!entry.header && entry.tabIndex >= 0 && entry.tabIndex < tabs.size()) {
                        CreativeModeTab rowMaster = tabs.get(entry.tabIndex);
                        if (rowMaster != selectedGroupMaster && OrganizerSettings.isTabGroup(rowMaster)) {
                            groupDropTargetMaster = rowMaster;
                        }
                    }
                }
            }
            return true;
        }
'''
if old_drag not in source:
    raise SystemExit("Could not replace nested-child drag target logic")
source = source.replace(old_drag, new_drag, 1)

# Finish drag: transfer the selected child to a different group, or reorder it inside
# the current group when dropped on another child row.
old_finish = '''        CreativeModeTab master = selectedGroupMaster;
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
'''
new_finish = '''        CreativeModeTab master = selectedGroupMaster;
        CreativeModeTab moving = selectedGroupChild;
        int targetIndex = groupDropTargetIndex;
        CreativeModeTab targetMaster = groupDropTargetMaster;
        boolean after = groupDropAfter;
        draggingGroupChild = false;
        groupDropTargetIndex = -1;
        groupDropTargetMaster = null;

        if (master == null || moving == null) return;

        if (targetMaster != null && targetMaster != master) {
            if (!OrganizerSettings.moveMergedTabToGroup(master, moving, targetMaster)) return;
            selectedGroupMaster = targetMaster;
            selectedGroupChild = moving;
            OrganizerSettings.setLayout(tabs, pageSizes);
            statusMessage = "Вкладку переміщено до іншої групи.";
            statusIsError = false;
            return;
        }

        if (targetIndex < 0) return;
        List<CreativeModeTab> children = OrganizerSettings.getMergedTabs(master);
        if (targetIndex >= children.size()) return;
        CreativeModeTab target = children.get(targetIndex);
        if (!OrganizerSettings.moveMergedTab(master, moving, target, after)) return;

        OrganizerSettings.setLayout(tabs, pageSizes);
        statusMessage = "Порядок вкладок усередині групи змінено.";
        statusIsError = false;
'''
if old_finish not in source:
    raise SystemExit("Could not replace nested-child drag completion")
source = source.replace(old_finish, new_finish, 1)

# Main tab dropped on a group master becomes a child of that group instead of
# being reordered beside it.
needle = '''        CreativeModeTab moving = tabs.get(sourceIndex);
        CreativeModeTab targetTab = targetIndex >= 0 && targetIndex < tabs.size() ? tabs.get(targetIndex) : null;
        if (targetTab == moving) return;

        int sourcePage = OrganizerSettings.getPageIndexForTabIndex(sourceIndex, pageSizes);
'''
replacement = '''        CreativeModeTab moving = tabs.get(sourceIndex);
        CreativeModeTab targetTab = targetIndex >= 0 && targetIndex < tabs.size() ? tabs.get(targetIndex) : null;
        if (targetTab == moving) return;

        if (targetTab != null && OrganizerSettings.isTabGroup(targetTab)) {
            moveMainTabIntoGroup(sourceIndex, targetTab);
            return;
        }

        int sourcePage = OrganizerSettings.getPageIndexForTabIndex(sourceIndex, pageSizes);
'''
if needle not in source:
    raise SystemExit("Could not add main-tab-to-group drop detection")
source = source.replace(needle, replacement, 1)

# Add the main-tab-to-group move helper just before moveTabToHeap.
needle = '    private void moveTabToHeap(int sourceIndex) {'
helper = '''    private void moveMainTabIntoGroup(int sourceIndex, CreativeModeTab targetMaster) {
        if (sourceIndex < 0 || sourceIndex >= tabs.size() || targetMaster == null) return;
        if (tabs.size() <= 1) {
            statusMessage = "Потрібно залишити хоча б одну видиму вкладку.";
            statusIsError = true;
            return;
        }

        int sourcePage = OrganizerSettings.getPageIndexForTabIndex(sourceIndex, pageSizes);
        if (sourcePage < 0) return;

        saveCurrentPageTitle();
        saveCurrentTabName();
        CreativeModeTab moving = tabs.remove(sourceIndex);
        if (sourcePage < pageSizes.size()) {
            int newSize = pageSizes.get(sourcePage) - 1;
            if (newSize <= 0) {
                pageSizes.remove(sourcePage);
                OrganizerSettings.removePageAndShiftNames(sourcePage);
                editingPageIndex = -1;
            } else {
                pageSizes.set(sourcePage, newSize);
            }
        }

        if (!OrganizerSettings.addTabToGroup(targetMaster, moving)) {
            tabs.add(Math.max(0, Math.min(sourceIndex, tabs.size())), moving);
            pageSizes = OrganizerSettings.getPageSizes(tabs.size());
            statusMessage = "Не вдалося додати вкладку до групи.";
            statusIsError = true;
            return;
        }

        selectedIndex = Math.max(0, tabs.indexOf(targetMaster));
        mergeSelection.clear();
        groupSelection.clear();
        selectedGroupMaster = targetMaster;
        selectedGroupChild = moving;
        OrganizerSettings.setLayout(tabs, pageSizes);
        updatePageEditor(true);
        ensureSelectionVisible();
        statusMessage = "Вкладку додано до групи.";
        statusIsError = false;
    }

''' + needle
if needle not in source:
    raise SystemExit("Could not locate moveTabToHeap for group move helper")
source = source.replace(needle, helper, 1)

# Reset transient destination state as part of all drag cleanup.
source = source.replace(
    '        draggingGroupChild = false;\n        groupDropTargetIndex = -1;\n',
    '        draggingGroupChild = false;\n        groupDropTargetIndex = -1;\n        groupDropTargetMaster = null;\n',
    1
)

screen.write_text(source)

# ---------------------------------------------------------------------------
# 3) Make the page title overlay render after vanilla pagination widgets.
#    A renderable added at the end of init is drawn after existing widgets.
# ---------------------------------------------------------------------------
accessor = BASE / "mixin/accessor/ScreenAccessor.java"
source = accessor.read_text()
if "taborganizer$addRenderableOnly" not in source:
    needle = '''    <T extends GuiEventListener & Renderable & NarratableEntry> T taborganizer$addRenderableWidget(T widget);
'''
    replacement = needle + '''
    @Invoker(value = "addRenderableOnly", remap = false)
    <T extends Renderable> T taborganizer$addRenderableOnly(T renderable);
'''
    if needle not in source:
        raise SystemExit("Could not locate ScreenAccessor widget invoker")
    source = source.replace(needle, replacement, 1)
    accessor.write_text(source)

mixin = BASE / "mixin/CreativeModeInventoryScreenMixin.java"
source = mixin.read_text()

# Remove the previous render-tail label injector and replace it with a reusable draw method.
render_start = source.find('    @Inject(method = "render",')
click_start = source.find('    @Inject(method = "mouseClicked"', render_start)
if render_start < 0 or click_start < 0:
    raise SystemExit("Could not locate old page-title renderer and click handler")
source = source[:render_start] + source[click_start:]

# Add an init-tail renderable. Since it is appended after the vanilla controls,
# it paints the plaque above (and fully covers) the vanilla page counter.
init_inject = r'''    @Inject(method = "init", at = @At("TAIL"), remap = false)
    private void taborganizer$registerPageHeadingOverlay(CallbackInfo ci) {
        ScreenAccessor accessor = (ScreenAccessor) (Object) this;
        accessor.taborganizer$addRenderableOnly(
                (net.minecraft.client.gui.components.Renderable) (graphics, mouseX, mouseY, partialTick) ->
                        taborganizer$drawPageHeading(graphics));
    }

    private void taborganizer$drawPageHeading(GuiGraphics graphics) {
        CreativeModeInventoryScreen screen = (CreativeModeInventoryScreen) (Object) this;
        CreativeModeInventoryScreenAccessor accessor = (CreativeModeInventoryScreenAccessor) (Object) this;
        List<CreativeTabsScreenPage> pages = accessor.taborganizer$getPages();

        int pageIndex = pages.indexOf(screen.getCurrentPage());
        if (pageIndex < 0) return;

        String title = OrganizerSettings.getPageName(pageIndex);
        String label = "Сторінка " + (pageIndex + 1) + (title.isBlank() ? "" : ": " + title);

        var font = Minecraft.getInstance().font;
        AbstractContainerScreenAccessor dimensions = (AbstractContainerScreenAccessor) (Object) this;
        int boxX = dimensions.taborganizer$getLeftPos() + 24;
        int boxY = dimensions.taborganizer$getTopPos() - 50;
        int boxWidth = Math.max(40, dimensions.taborganizer$getImageWidth() - 48);
        int boxHeight = 20;
        int contentX = boxX + 8;
        int contentWidth = boxWidth - 16;

        // This opaque plaque is drawn after the vanilla renderables, so the old
        // page counter cannot bleed through the custom title.
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
pos = source.rfind("\n}")
if pos < 0:
    raise SystemExit("Could not locate closing brace for inventory screen mixin")
source = source[:pos] + "\n\n" + init_inject + source[pos:]

# The click handler uses the exact same plaque geometry.
mixin.write_text(source)

# ---------------------------------------------------------------------------
# 4) Bump the mod version.
# ---------------------------------------------------------------------------
props = ROOT / "gradle.properties"
text = props.read_text()
text, count = re.subn(r"(?m)^mod_version=.*$", "mod_version=1.1.0", text, count=1)
if count != 1:
    raise SystemExit("Could not update gradle.properties to 1.1.0")
props.write_text(text)

toml = ROOT / "src/main/resources/META-INF/neoforge.mods.toml"
if toml.exists():
    text = toml.read_text()
    text = re.sub(r'(?m)^(version\s*=\s*")[^"]+(".*)$', r'\g<1>1.1.0\2', text)
    toml.write_text(text)

print("Applied beta 1.1.0: plus-to-create groups, drag-to-group and group-to-group transfer, drag reorder, compact controls, and a topmost page-title overlay.")
