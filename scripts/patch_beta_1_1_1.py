from pathlib import Path
import re

ROOT = Path(".")
BASE = ROOT / "src/main/java/com/example/taborganizer"

# ---------------------------------------------------------------------------
# 1) Allow a grouped tab to be dragged back into the main page list.
#    Drop on a normal tab = insert before/after it.
#    Drop on a page header = insert at the start of that page.
#    Drop on another group = transfer to that group.
# ---------------------------------------------------------------------------
screen = BASE / "client/gui/OrganizerScreen.java"
source = screen.read_text()

# Add destinations for ungrouping a child into the main list.
if "groupDropMainTabIndex" not in source:
    needle = '    private CreativeModeTab groupDropTargetMaster;\n'
    replacement = needle + (
        '    private int groupDropMainTabIndex = -1;\n'
        '    private int groupDropPageIndex = -1;\n'
        '    private boolean groupDropMainAfter;\n'
    )
    if needle not in source:
        raise SystemExit("Could not find groupDropTargetMaster field")
    source = source.replace(needle, replacement, 1)

# Make the drag destination easy to understand in the editor.
source = source.replace(
    'Component.literal("Ctrl+клік: вибирай вкладки або окремі елементи групи")',
    'Component.literal("Перетягування: між групами або назад на сторінку")',
    1
)

# Remove the duplicate Done button; Escape and Save & Close already close the editor.
done_marker = '        this.addRenderableWidget(Button.builder(Component.translatable("gui.done"), button -> onClose())'
done_start = source.find(done_marker)
if done_start >= 0:
    done_end = source.find('.build());', done_start)
    if done_end < 0:
        raise SystemExit("Could not locate end of duplicate Done button")
    done_end = source.find('\n', done_end)
    source = source[:done_start] + source[done_end + 1:]

# Remove the redundant Done button; Escape and Save & Close already close the editor.
done_marker = '        this.addRenderableWidget(Button.builder(Component.translatable("gui.done"), button -> onClose())'
done_start = source.find(done_marker)
if done_start >= 0:
    done_end = source.find('.build());', done_start)
    if done_end < 0:
        raise SystemExit("Could not locate end of duplicate Done button")
    done_end = source.find('\n', done_end)
    source = source[:done_start] + source[done_end + 1:]

# Put the current status and the ungrouping hint in a compact footer.
status_old = '''        if (!statusMessage.isBlank()) {
            graphics.drawString(this.font, trimToWidth(statusMessage, RIGHT_WIDTH), rightX, y + 290,
                    statusIsError ? 0xFFFF7777 : 0xFF9FE3A7, false);
        }
'''
status_new = '''        if (!statusMessage.isBlank()) {
            graphics.drawString(this.font, trimToWidth(statusMessage, RIGHT_WIDTH), rightX, y + 268,
                    statusIsError ? 0xFFFF7777 : 0xFF9FE3A7, false);
        }
        graphics.drawString(this.font,
                trimToWidth("Перетягни вкладку з групи на рядок або заголовок сторінки, щоб повернути її.", RIGHT_WIDTH),
                rightX, y + 284, 0xFF9BA8B6, false);
'''
if status_old in source:
    source = source.replace(status_old, status_new, 1)

# Selecting a child starts a drag. Clear every previous drop destination at the start.
source = source.replace(
    '''                    groupDropTargetMaster = null;
                    dragIndex = -1;
''',
    '''                    groupDropTargetMaster = null;
                    groupDropMainTabIndex = -1;
                    groupDropPageIndex = -1;
                    dragIndex = -1;
''',
    1
)

# Recognize three types of destination while dragging a child:
#  - a sibling child in the same group (reorder),
#  - another group's row (transfer),
#  - any normal tab row or page header (ungroup into the main list).
old_drag = '''        if (button == 0 && draggingGroupChild) {
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
new_drag = '''        if (button == 0 && draggingGroupChild) {
            groupDropTargetIndex = -1;
            groupDropTargetMaster = null;
            groupDropMainTabIndex = -1;
            groupDropPageIndex = -1;

            if (isInsideTabList(mouseX, mouseY)) {
                int entryIndex = rowIndexAt(mouseY);
                List<ListEntry> entries = buildListEntries();
                if (entryIndex >= 0 && entryIndex < entries.size()) {
                    ListEntry entry = entries.get(entryIndex);
                    double rowY = listTop() + (entryIndex - scrollOffset) * ROW_HEIGHT;
                    boolean after = mouseY >= rowY + ROW_HEIGHT / 2.0;

                    if (entry.header) {
                        // Dropping on "Сторінка N" returns the child to that page.
                        groupDropPageIndex = entry.pageIndex;
                    } else if (entry.subgroup && entry.tabIndex >= 0 && entry.tabIndex < tabs.size()) {
                        CreativeModeTab rowMaster = tabs.get(entry.tabIndex);
                        if (rowMaster == selectedGroupMaster && entry.childTab != selectedGroupChild) {
                            groupDropTargetIndex = OrganizerSettings.getMergedTabs(selectedGroupMaster).indexOf(entry.childTab);
                            groupDropAfter = after;
                        } else if (rowMaster != selectedGroupMaster && OrganizerSettings.isTabGroup(rowMaster)) {
                            groupDropTargetMaster = rowMaster;
                        }
                    } else if (!entry.header && entry.tabIndex >= 0 && entry.tabIndex < tabs.size()) {
                        CreativeModeTab rowMaster = tabs.get(entry.tabIndex);
                        if (rowMaster != selectedGroupMaster && OrganizerSettings.isTabGroup(rowMaster)) {
                            // Drop on another group's main row to transfer the child.
                            groupDropTargetMaster = rowMaster;
                        } else {
                            // Drop on an ordinary row (or its former parent) to ungroup.
                            groupDropMainTabIndex = entry.tabIndex;
                            groupDropMainAfter = rowMaster == selectedGroupMaster || after;
                        }
                    }
                }
            }
            return true;
        }
'''
if old_drag not in source:
    raise SystemExit("Could not replace group-child drag destination logic")
source = source.replace(old_drag, new_drag, 1)

# Highlight page headers and ordinary rows as valid ungrouping drop zones.
source = source.replace(
    'boolean targeted = taborganizer$isDragging() && !dropToHeap && dropEntryIndex == entryIndex;',
    'boolean targeted = (taborganizer$isDragging() && !dropToHeap && dropEntryIndex == entryIndex)\n'
    '                        || (draggingGroupChild && groupDropPageIndex == entry.pageIndex);',
    1
)
source = source.replace(
    '''                if (draggingGroupChild && groupDropTargetMaster == tab) {
                    graphics.renderOutline(listX + 1, rowY + 1, LIST_WIDTH - 2, ROW_HEIGHT - 2, 0xFFFFD477);
                }
''',
    '''                if (draggingGroupChild && (groupDropTargetMaster == tab || groupDropMainTabIndex == index)) {
                    graphics.renderOutline(listX + 1, rowY + 1, LIST_WIDTH - 2, ROW_HEIGHT - 2, 0xFFFFD477);
                }
''',
    1
)

# Replace group-child drag completion and add the actual ungroup-to-list operation.
start = source.find("    private void finishGroupChildDrag() {")
end = source.find("\n    private static final class ListEntry", start)
if start < 0 or end < 0:
    raise SystemExit("Could not locate finishGroupChildDrag method")

methods = '''    private void restoreGroupChildToMain(
            CreativeModeTab sourceMaster,
            CreativeModeTab moving,
            int targetMainTabIndex,
            int targetPageIndex,
            boolean after) {
        if (sourceMaster == null || moving == null) return;

        int removed = OrganizerSettings.removeMergedTabs(sourceMaster, List.of(moving));
        if (removed <= 0) {
            statusMessage = "Не вдалося витягнути вкладку з групи.";
            statusIsError = true;
            return;
        }

        int destinationPage = targetPageIndex;
        int insertIndex;

        if (targetMainTabIndex >= 0 && targetMainTabIndex < tabs.size()) {
            destinationPage = OrganizerSettings.getPageIndexForTabIndex(targetMainTabIndex, pageSizes);
            insertIndex = targetMainTabIndex + (after ? 1 : 0);
        } else {
            if (destinationPage < 0 || destinationPage >= pageSizes.size()) {
                int masterIndex = tabs.indexOf(sourceMaster);
                destinationPage = masterIndex >= 0
                        ? OrganizerSettings.getPageIndexForTabIndex(masterIndex, pageSizes)
                        : Math.max(0, Math.min(editingPageIndex, pageSizes.size() - 1));
            }
            if (destinationPage < 0 || destinationPage >= pageSizes.size()) {
                destinationPage = Math.max(0, pageSizes.size() - 1);
            }
            insertIndex = OrganizerSettings.pageStart(pageSizes, destinationPage);
        }

        if (destinationPage < 0 || destinationPage >= pageSizes.size()) {
            // Defensive fallback: keep the restored tab in the final available page.
            destinationPage = Math.max(0, pageSizes.size() - 1);
            insertIndex = tabs.size();
        }

        insertIndex = Math.max(0, Math.min(tabs.size(), insertIndex));
        tabs.add(insertIndex, moving);
        pageSizes.set(destinationPage, pageSizes.get(destinationPage) + 1);
        spillOverflowIntoFollowingPages();

        selectedIndex = tabs.indexOf(moving);
        selectedGroupMaster = null;
        selectedGroupChild = null;
        groupSelection.clear();
        mergeSelection.clear();

        OrganizerSettings.setLayout(tabs, pageSizes);
        OrganizerSettings.save();
        updatePageEditor(true);
        ensureSelectionVisible();

        statusMessage = "Вкладку повернуто до основного списку.";
        statusIsError = false;
    }

    private void finishGroupChildDrag() {
        CreativeModeTab master = selectedGroupMaster;
        CreativeModeTab moving = selectedGroupChild;
        int targetIndex = groupDropTargetIndex;
        CreativeModeTab targetMaster = groupDropTargetMaster;
        int targetMainTabIndex = groupDropMainTabIndex;
        int targetPageIndex = groupDropPageIndex;
        boolean after = groupDropAfter || groupDropMainAfter;

        draggingGroupChild = false;
        groupDropTargetIndex = -1;
        groupDropTargetMaster = null;
        groupDropMainTabIndex = -1;
        groupDropPageIndex = -1;

        if (master == null || moving == null) return;

        // Move into another group.
        if (targetMaster != null && targetMaster != master) {
            if (!OrganizerSettings.moveMergedTabToGroup(master, moving, targetMaster)) return;
            selectedGroupMaster = targetMaster;
            selectedGroupChild = moving;
            OrganizerSettings.setLayout(tabs, pageSizes);
            OrganizerSettings.save();
            statusMessage = "Вкладку переміщено до іншої групи.";
            statusIsError = false;
            return;
        }

        // Reorder inside the current group.
        if (targetIndex >= 0) {
            List<CreativeModeTab> children = OrganizerSettings.getMergedTabs(master);
            if (targetIndex >= children.size()) return;
            CreativeModeTab target = children.get(targetIndex);
            if (!OrganizerSettings.moveMergedTab(master, moving, target, after)) return;

            OrganizerSettings.setLayout(tabs, pageSizes);
            OrganizerSettings.save();
            statusMessage = "Порядок вкладок усередині групи змінено.";
            statusIsError = false;
            return;
        }

        // Drop on a regular tab row or a page header to take this one tab out of its group.
        if (targetMainTabIndex >= 0 || targetPageIndex >= 0) {
            saveCurrentPageTitle();
            saveCurrentTabName();
            restoreGroupChildToMain(master, moving, targetMainTabIndex, targetPageIndex, after);
        }
    }
'''
source = source[:start] + methods + source[end:]

# Reset group drag destinations when the general drag state is cleared.
source = source.replace(
    '''        groupDropTargetMaster = null;
        dropToHeap = false;
''',
    '''        groupDropTargetMaster = null;
        groupDropMainTabIndex = -1;
        groupDropPageIndex = -1;
        dropToHeap = false;
''',
    1
)

screen.write_text(source)

# ---------------------------------------------------------------------------
# 2) Put the page-title plaque in renderLabels TAIL, after Minecraft paints
#    the vanilla page counter. Keep the visual and click geometry identical.
# ---------------------------------------------------------------------------
mixin = BASE / "mixin/CreativeModeInventoryScreenMixin.java"
source = mixin.read_text()

init_start = source.find('    @Inject(method = "init",')
class_end = source.rfind("\n}")
if init_start < 0 or class_end < 0:
    raise SystemExit("Could not locate the old init renderable overlay")

render_labels = r'''    @Inject(method = "renderLabels", at = @At("TAIL"), remap = false)
    private void taborganizer$renderPageHeading(GuiGraphics graphics, int mouseX, int mouseY, CallbackInfo ci) {
        CreativeModeInventoryScreen screen = (CreativeModeInventoryScreen) (Object) this;
        CreativeModeInventoryScreenAccessor accessor = (CreativeModeInventoryScreenAccessor) (Object) this;
        List<CreativeTabsScreenPage> pages = accessor.taborganizer$getPages();

        int pageIndex = pages.indexOf(screen.getCurrentPage());
        if (pageIndex < 0) return;

        String title = OrganizerSettings.getPageName(pageIndex);
        String label = "Сторінка " + (pageIndex + 1) + (title.isBlank() ? "" : ": " + title);

        var font = Minecraft.getInstance().font;
        AbstractContainerScreenAccessor dimensions = (AbstractContainerScreenAccessor) (Object) this;

        int boxX = 24;
        int boxY = -70;
        int boxWidth = Math.max(40, dimensions.taborganizer$getImageWidth() - 48);
        int boxHeight = 20;
        int contentX = boxX + 8;
        int contentWidth = boxWidth - 16;

        // renderLabels TAIL is deliberately after the vanilla 1 / N text,
        // so this opaque plaque fully covers it instead of sitting underneath it.
        graphics.fill(boxX, boxY, boxX + boxWidth, boxY + boxHeight, 0xFF202329);
        graphics.renderOutline(boxX, boxY, boxWidth, boxHeight, 0xFF98702C);

        int textWidth = font.width(label);
        int drawX;
        if (textWidth <= contentWidth) {
            drawX = contentX + (contentWidth - textWidth) / 2;
        } else {
            int overflow = textWidth - contentWidth;
            long dwellMillis = 1600L;
            long travelMillis = Math.max(2400L, overflow * 70L);
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
source = source[:init_start] + render_labels + source[class_end:]
mixin.write_text(source)

# Update the click target to the same screen-space position as the renderLabels plaque.
click_start = source.find('    @Inject(method = "mouseClicked"')
click_end = source.find('\n    }\n', click_start)
if click_start < 0 or click_end < 0:
    raise SystemExit("Could not find the existing page-heading click handler")
click_block = source[click_start:click_end + 7]
click_block = click_block.replace(
    'int boxY = dimensions.taborganizer$getTopPos() - 50;',
    'int boxY = dimensions.taborganizer$getTopPos() - 70;'
)
source = source[:click_start] + click_block + source[click_end + 7:]
mixin.write_text(source)

# ---------------------------------------------------------------------------
# 3) Bump the mod version.
# ---------------------------------------------------------------------------
props = ROOT / "gradle.properties"
text = props.read_text()
text, count = re.subn(r"(?m)^mod_version=.*$", "mod_version=1.1.1", text, count=1)
if count != 1:
    raise SystemExit("Could not update gradle.properties to 1.1.1")
props.write_text(text)

toml = ROOT / "src/main/resources/META-INF/neoforge.mods.toml"
if toml.exists():
    text = toml.read_text()
    text = re.sub(r'(?m)^(version\s*=\s*")[^"]+(".*)$', r'\g<1>1.1.1\2', text)
    toml.write_text(text)

print("Applied beta 1.1.1: drag a grouped tab to any main row/page header to ungroup it; draw page plaque after the vanilla counter; cleaner editor footer.")
