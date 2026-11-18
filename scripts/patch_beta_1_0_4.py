from pathlib import Path
import re

ROOT = Path(".")
BASE = ROOT / "src/main/java/com/example/taborganizer"

screen_source = r'''package com.example.taborganizer.client.gui;

import com.example.taborganizer.config.OrganizerSettings;
import com.example.taborganizer.mixin.accessor.ClientPacketListenerAccessor;
import com.example.taborganizer.mixin.accessor.CreativeModeInventoryScreenAccessor;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.components.Button;
import net.minecraft.client.gui.components.EditBox;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.client.gui.screens.inventory.CreativeModeInventoryScreen;
import net.minecraft.client.multiplayer.ClientPacketListener;
import net.minecraft.network.chat.Component;
import net.minecraft.world.flag.FeatureFlagSet;
import net.minecraft.world.item.CreativeModeTab;

import java.util.ArrayList;
import java.util.List;

/** Drag-and-drop editor for creative tab pages, page sizes, page headings and a temporary holding heap. */
public final class OrganizerScreen extends Screen {
    private static final int PANEL_WIDTH = 720;
    private static final int PANEL_HEIGHT = 312;
    private static final int ROW_HEIGHT = 18;
    private static final int VISIBLE_ROWS = 12;
    private static final int HEAP_WIDTH = 120;
    private static final int LIST_WIDTH = 280;
    private static final int LIST_X_OFFSET = 146;
    private static final int RIGHT_X_OFFSET = 444;
    private static final int RIGHT_WIDTH = 250;

    private final Screen parentScreen;
    private final List<CreativeModeTab> tabs = new ArrayList<>();
    private final List<CreativeModeTab> heapTabs = new ArrayList<>();
    private List<Integer> pageSizes = new ArrayList<>();
    private int selectedIndex = 0;
    private int scrollOffset = 0;
    private int heapScrollOffset = 0;
    private int editingPageIndex = -1;

    private int dragIndex = -1;
    private int heapDragIndex = -1;
    private boolean draggingHeap;
    private boolean dropToHeap;
    private int dropEntryIndex = -1;
    private int dropPageIndex = -1;
    private int dropTabIndex = -1;
    private boolean dropAfter;
    private String statusMessage = "";
    private boolean statusIsError;

    private int panelX;
    private int panelY;
    private EditBox pageNameField;
    private EditBox pageSizeField;

    public OrganizerScreen(Screen parentScreen) {
        super(Component.translatable("screen.taborganizer.title"));
        this.parentScreen = parentScreen;
        this.tabs.addAll(OrganizerSettings.getEditableTabs());
        this.pageSizes = OrganizerSettings.getPageSizes(tabs.size());
    }

    @Override
    protected void init() {
        panelX = (this.width - PANEL_WIDTH) / 2;
        panelY = (this.height - PANEL_HEIGHT) / 2;

        int rightX = panelX + RIGHT_X_OFFSET;
        int rightWidth = RIGHT_WIDTH;

        pageNameField = new EditBox(this.font, rightX, panelY + 96, rightWidth, 20,
                Component.translatable("screen.taborganizer.page_name"));
        pageNameField.setMaxLength(48);
        this.addRenderableWidget(pageNameField);

        pageSizeField = new EditBox(this.font, rightX, panelY + 139, 44, 20,
                Component.translatable("screen.taborganizer.page_size"));
        pageSizeField.setMaxLength(2);
        pageSizeField.setFilter(value -> value.isEmpty() || value.chars().allMatch(Character::isDigit));
        this.addRenderableWidget(pageSizeField);
        updatePageEditor(true);

        this.addRenderableWidget(Button.builder(Component.translatable("screen.taborganizer.apply_size"), button -> applyPageSize())
                .bounds(rightX + 52, panelY + 139, rightWidth - 52, 20).build());

        this.addRenderableWidget(Button.builder(Component.translatable("screen.taborganizer.reset"), button -> {
            saveCurrentPageTitle();
            OrganizerSettings.resetOrder();
            tabs.clear();
            tabs.addAll(OrganizerSettings.getEditableTabs());
            heapTabs.clear();
            pageSizes = OrganizerSettings.getPageSizes(tabs.size());
            selectedIndex = 0;
            scrollOffset = 0;
            heapScrollOffset = 0;
            statusMessage = Component.translatable("screen.taborganizer.reset_done").getString();
            statusIsError = false;
            updatePageEditor(true);
        }).bounds(rightX, panelY + 170, rightWidth, 20).build());

        this.addRenderableWidget(Button.builder(Component.translatable("screen.taborganizer.save"), button -> {
            if (!heapTabs.isEmpty()) {
                setHeapReturnWarning();
                return;
            }
            saveCurrentPageTitle();
            OrganizerSettings.setLayout(tabs, pageSizes);
            OrganizerSettings.save();
            onClose();
        }).bounds(rightX, panelY + 198, rightWidth, 20).build());

        this.addRenderableWidget(Button.builder(Component.translatable("gui.done"), button -> onClose())
                .bounds(rightX, panelY + 226, rightWidth, 20).build());
    }

    private static final class ListEntry {
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

    private int pageIndexForSelection() {
        if (tabs.isEmpty()) return 0;
        return OrganizerSettings.getPageIndexForTabIndex(Math.max(0, selectedIndex), pageSizes);
    }

    private void saveCurrentPageTitle() {
        if (editingPageIndex >= 0 && pageNameField != null) {
            OrganizerSettings.setPageName(editingPageIndex, pageNameField.getValue());
        }
    }

    private void updatePageEditor(boolean force) {
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

    private void applyPageSize() {
        saveCurrentPageTitle();
        if (editingPageIndex < 0 || editingPageIndex >= pageSizes.size()) return;
        try {
            int requested = Integer.parseInt(pageSizeField.getValue());
            if (requested < 1 || requested > OrganizerSettings.MAX_TABS_PER_PAGE) {
                throw new NumberFormatException("out of range");
            }
            pageSizes = OrganizerSettings.resizePage(editingPageIndex, requested, tabs.size());
            OrganizerSettings.setLayout(tabs, pageSizes);
            editingPageIndex = -1;
            selectedIndex = Math.min(selectedIndex, Math.max(0, tabs.size() - 1));
            statusMessage = Component.translatable("screen.taborganizer.size_applied").getString();
            statusIsError = false;
            updatePageEditor(true);
            ensureSelectionVisible();
        } catch (NumberFormatException exception) {
            statusMessage = Component.translatable("screen.taborganizer.size_error").getString();
            statusIsError = true;
            pageSizeField.setValue(editingPageIndex >= 0 && editingPageIndex < pageSizes.size()
                    ? Integer.toString(pageSizes.get(editingPageIndex)) : "1");
        }
    }

    private void setHeapReturnWarning() {
        statusMessage = "Поверни всі вкладки з Heap у список перед збереженням.";
        statusIsError = true;
    }

    @Override
    public void render(GuiGraphics graphics, int mouseX, int mouseY, float partialTick) {
        int x = panelX;
        int y = panelY;
        graphics.fill(x, y, x + PANEL_WIDTH, y + PANEL_HEIGHT, 0xF0202329);
        graphics.renderOutline(x, y, PANEL_WIDTH, PANEL_HEIGHT, 0xFF707780);

        graphics.drawString(this.font, this.title, x + 12, y + 10, 0xFFFFFF, false);
        graphics.drawString(this.font, Component.translatable("screen.taborganizer.hint"),
                x + 12, y + 25, 0xB8C0CC, false);

        int listY = listTop();
        int listHeight = VISIBLE_ROWS * ROW_HEIGHT;
        int heapX = x + 12;
        int listX = x + LIST_X_OFFSET;
        int rightX = x + RIGHT_X_OFFSET;

        // Temporary holding heap: tabs can be parked here while scrolling to another page.
        graphics.drawString(this.font, Component.literal("HEAP / ТИМЧАСОВО"), heapX, y + 39, 0xE7BE72, false);
        graphics.fill(heapX, listY, heapX + HEAP_WIDTH, listY + listHeight, 0xFF15181D);
        for (int visible = 0; visible < VISIBLE_ROWS; visible++) {
            int index = heapScrollOffset + visible;
            if (index >= heapTabs.size()) break;
            int rowY = listY + visible * ROW_HEIGHT;
            boolean dragging = draggingHeap && heapDragIndex == index;
            int bg = dragging ? 0xFF6A5135 : 0xFF252B33;
            graphics.fill(heapX + 1, rowY + 1, heapX + HEAP_WIDTH - 1, rowY + ROW_HEIGHT - 1, bg);
            CreativeModeTab tab = heapTabs.get(index);
            graphics.renderItem(tab.getIconItem(), heapX + 5, rowY + 1);
            graphics.drawString(this.font, trimToWidth(tab.getDisplayName().getString(), HEAP_WIDTH - 34),
                    heapX + 27, rowY + 5, 0xF2F2F2, false);
        }
        if (heapTabs.isEmpty()) {
            graphics.drawString(this.font, "Перетягни", heapX + 10, listY + 92, 0xAEB6C1, false);
            graphics.drawString(this.font, "вкладку сюди", heapX + 5, listY + 106, 0xAEB6C1, false);
        }
        if (dropToHeap && dragIndex >= 0) {
            graphics.renderOutline(heapX, listY, HEAP_WIDTH, listHeight, 0xFFFFD477);
        }
        renderHeapScrollbar(graphics, heapX, listY, listHeight);

        // Main page list.
        graphics.drawString(this.font, Component.literal("СТОРІНКИ ТА ВКЛАДКИ"), listX, y + 39, 0xE7BE72, false);
        graphics.fill(listX, listY, listX + LIST_WIDTH, listY + listHeight, 0xFF15181D);

        List<ListEntry> entries = buildListEntries();
        for (int visible = 0; visible < VISIBLE_ROWS; visible++) {
            int entryIndex = scrollOffset + visible;
            if (entryIndex >= entries.size()) break;
            ListEntry entry = entries.get(entryIndex);
            int rowY = listY + visible * ROW_HEIGHT;

            if (entry.header) {
                boolean targeted = isDragging() && !dropToHeap && dropEntryIndex == entryIndex;
                int bg = targeted ? 0xFF5D5838 : 0xFF344252;
                graphics.fill(listX + 1, rowY + 1, listX + LIST_WIDTH - 1, rowY + ROW_HEIGHT - 1, bg);
                int count = pageSizes.get(entry.pageIndex);
                String title = OrganizerSettings.getPageName(entry.pageIndex);
                if (title.isBlank()) title = Component.translatable("screen.taborganizer.unnamed_page").getString();
                String label = Component.translatable("screen.taborganizer.page_header", entry.pageIndex + 1, title, count).getString();
                graphics.drawString(this.font, trimToWidth(label, LIST_WIDTH - 12), listX + 7, rowY + 5, 0xFFFFFF, false);
                if (targeted) graphics.renderOutline(listX + 1, rowY + 1, LIST_WIDTH - 2, ROW_HEIGHT - 2, 0xFFFFD477);
            } else {
                int index = entry.tabIndex;
                boolean selected = index == selectedIndex;
                boolean dragging = !draggingHeap && index == dragIndex;
                int background = dragging ? 0xFF6A5135 : (selected ? 0xFF465A73 : 0xFF252B33);
                graphics.fill(listX + 1, rowY + 1, listX + LIST_WIDTH - 1, rowY + ROW_HEIGHT - 1, background);

                if (isDragging() && !dropToHeap && dropEntryIndex == entryIndex) {
                    int lineY = dropAfter ? rowY + ROW_HEIGHT - 2 : rowY + 1;
                    graphics.fill(listX + 2, lineY, listX + LIST_WIDTH - 2, lineY + 2, 0xFFFFD477);
                }

                CreativeModeTab tab = tabs.get(index);
                graphics.renderItem(tab.getIconItem(), listX + 11, rowY + 1);
                graphics.drawString(this.font, trimToWidth(tab.getDisplayName().getString(), LIST_WIDTH - 42),
                        listX + 34, rowY + 5, 0xF2F2F2, false);
            }
        }
        renderListScrollbar(graphics, listX, listY, listHeight, entries.size());

        int pageCount = pageSizes.size();
        int displayedPage = editingPageIndex >= 0 ? editingPageIndex + 1 : 1;
        int displayedSize = editingPageIndex >= 0 && editingPageIndex < pageSizes.size() ? pageSizes.get(editingPageIndex) : 0;
        graphics.drawString(this.font, Component.translatable("screen.taborganizer.page_label", displayedPage, pageCount),
                rightX, y + 48, 0xFFFFFF, false);
        int firstTab = editingPageIndex >= 0 && editingPageIndex < pageSizes.size()
                ? OrganizerSettings.pageStart(pageSizes, editingPageIndex) + 1 : 0;
        int lastTab = editingPageIndex >= 0 && editingPageIndex < pageSizes.size()
                ? firstTab + displayedSize - 1 : 0;
        graphics.drawString(this.font, Component.translatable("screen.taborganizer.page_range", firstTab, lastTab),
                rightX, y + 63, 0xB8C0CC, false);
        graphics.drawString(this.font, Component.translatable("screen.taborganizer.name_prompt"),
                rightX, y + 82, 0xE3E7ED, false);
        graphics.drawString(this.font, Component.translatable("screen.taborganizer.size_prompt"),
                rightX, y + 125, 0xE3E7ED, false);
        graphics.drawString(this.font, Component.literal("Перетягни вкладку в Heap, щоб тимчасово відкласти її."),
                x + 12, y + 285, 0xB8C0CC, false);
        if (!statusMessage.isBlank()) {
            graphics.drawString(this.font, trimToWidth(statusMessage, RIGHT_WIDTH), rightX, y + 260,
                    statusIsError ? 0xFFFF7777 : 0xFF9FE3A7, false);
        }

        super.render(graphics, mouseX, mouseY, partialTick);
    }

    private void renderHeapScrollbar(GuiGraphics graphics, int heapX, int listY, int listHeight) {
        if (heapTabs.size() <= VISIBLE_ROWS) return;
        int thumbHeight = Math.max(18, listHeight * VISIBLE_ROWS / heapTabs.size());
        int maxOffset = heapTabs.size() - VISIBLE_ROWS;
        int thumbY = listY + (listHeight - thumbHeight) * heapScrollOffset / maxOffset;
        graphics.fill(heapX + HEAP_WIDTH - 4, listY + 2, heapX + HEAP_WIDTH - 2, listY + listHeight - 2, 0xFF3D434B);
        graphics.fill(heapX + HEAP_WIDTH - 5, thumbY, heapX + HEAP_WIDTH - 1, thumbY + thumbHeight, 0xFFB5BBC4);
    }

    private void renderListScrollbar(GuiGraphics graphics, int listX, int listY, int listHeight, int entryCount) {
        if (entryCount <= VISIBLE_ROWS) return;
        int thumbHeight = Math.max(18, listHeight * VISIBLE_ROWS / entryCount);
        int maxOffset = entryCount - VISIBLE_ROWS;
        int thumbY = listY + (listHeight - thumbHeight) * scrollOffset / maxOffset;
        graphics.fill(listX + LIST_WIDTH - 4, listY + 2, listX + LIST_WIDTH - 2, listY + listHeight - 2, 0xFF3D434B);
        graphics.fill(listX + LIST_WIDTH - 5, thumbY, listX + LIST_WIDTH - 1, thumbY + thumbHeight, 0xFFB5BBC4);
    }

    private boolean isDragging() {
        return dragIndex >= 0 || draggingHeap;
    }

    private String trimToWidth(String text, int maxWidth) {
        if (this.font.width(text) <= maxWidth) return text;
        while (!text.isEmpty() && this.font.width(text + "…") > maxWidth) {
            text = text.substring(0, text.length() - 1);
        }
        return text + "…";
    }

    @Override
    public boolean mouseClicked(double mouseX, double mouseY, int button) {
        if (button == 0 && isInsideHeap(mouseX, mouseY)) {
            int index = heapRowIndexAt(mouseY);
            if (index >= 0 && index < heapTabs.size()) {
                draggingHeap = true;
                heapDragIndex = index;
                dragIndex = -1;
                dropEntryIndex = -1;
                dropPageIndex = -1;
                dropTabIndex = -1;
                dropToHeap = false;
                return true;
            }
        }

        if (button == 0 && isInsideTabList(mouseX, mouseY)) {
            int entryIndex = rowIndexAt(mouseY);
            List<ListEntry> entries = buildListEntries();
            if (entryIndex >= 0 && entryIndex < entries.size()) {
                ListEntry entry = entries.get(entryIndex);
                if (entry.header) {
                    saveCurrentPageTitle();
                    selectedIndex = Math.min(OrganizerSettings.pageStart(pageSizes, entry.pageIndex), Math.max(0, tabs.size() - 1));
                    updatePageEditor(true);
                    return true;
                }
                selectedIndex = entry.tabIndex;
                dragIndex = entry.tabIndex;
                draggingHeap = false;
                heapDragIndex = -1;
                dropEntryIndex = -1;
                dropPageIndex = -1;
                dropTabIndex = -1;
                dropToHeap = false;
                updatePageEditor(false);
                return true;
            }
        }
        return super.mouseClicked(mouseX, mouseY, button);
    }

    @Override
    public boolean mouseDragged(double mouseX, double mouseY, int button, double dragX, double dragY) {
        if (button == 0 && dragIndex >= 0 && isInsideHeap(mouseX, mouseY)) {
            dropToHeap = true;
            dropEntryIndex = -1;
            dropPageIndex = -1;
            dropTabIndex = -1;
            return true;
        }
        if (button == 0 && isDragging() && isInsideTabList(mouseX, mouseY)) {
            dropToHeap = false;
            int entryIndex = rowIndexAt(mouseY);
            List<ListEntry> entries = buildListEntries();
            if (entryIndex >= 0 && entryIndex < entries.size()) {
                ListEntry entry = entries.get(entryIndex);
                dropEntryIndex = entryIndex;
                dropPageIndex = entry.pageIndex;
                dropTabIndex = entry.header ? -1 : entry.tabIndex;
                dropAfter = !entry.header && mouseY >= listTop() + (entryIndex - scrollOffset) * ROW_HEIGHT + ROW_HEIGHT / 2.0;
            }
            return true;
        }
        if (button == 0 && isDragging()) {
            dropToHeap = false;
            dropEntryIndex = -1;
            dropPageIndex = -1;
            dropTabIndex = -1;
            return true;
        }
        return super.mouseDragged(mouseX, mouseY, button, dragX, dragY);
    }

    @Override
    public boolean mouseReleased(double mouseX, double mouseY, int button) {
        if (button == 0 && isDragging()) {
            finishDrag();
            return true;
        }
        return super.mouseReleased(mouseX, mouseY, button);
    }

    private void clearDragState() {
        dragIndex = -1;
        heapDragIndex = -1;
        draggingHeap = false;
        dropToHeap = false;
        dropEntryIndex = -1;
        dropPageIndex = -1;
        dropTabIndex = -1;
    }

    private void finishDrag() {
        if (draggingHeap) {
            int sourceHeapIndex = heapDragIndex;
            int targetPage = dropPageIndex;
            int targetIndex = dropTabIndex;
            boolean after = dropAfter;
            clearDragState();
            moveHeapTabToPage(sourceHeapIndex, targetPage, targetIndex, after);
            return;
        }

        int sourceIndex = dragIndex;
        int targetPage = dropPageIndex;
        int targetIndex = dropTabIndex;
        boolean after = dropAfter;
        boolean toHeap = dropToHeap;
        clearDragState();

        if (sourceIndex < 0 || sourceIndex >= tabs.size()) return;
        if (toHeap) {
            moveTabToHeap(sourceIndex);
            return;
        }
        if (targetPage < 0 || targetPage >= pageSizes.size()) return;

        CreativeModeTab moving = tabs.get(sourceIndex);
        CreativeModeTab targetTab = targetIndex >= 0 && targetIndex < tabs.size() ? tabs.get(targetIndex) : null;
        if (targetTab == moving) return;

        int sourcePage = OrganizerSettings.getPageIndexForTabIndex(sourceIndex, pageSizes);
        if (sourcePage < 0) return;
        saveCurrentPageTitle();
        tabs.remove(sourceIndex);
        if (sourcePage != targetPage) {
            pageSizes.set(sourcePage, pageSizes.get(sourcePage) - 1);
            if (pageSizes.get(sourcePage) == 0) {
                pageSizes.remove(sourcePage);
                OrganizerSettings.removePageAndShiftNames(sourcePage);
                editingPageIndex = -1;
                if (sourcePage < targetPage) targetPage--;
            }
        }

        int insertIndex;
        if (targetTab != null) {
            int currentTargetIndex = tabs.indexOf(targetTab);
            if (currentTargetIndex < 0) return;
            insertIndex = currentTargetIndex + (after ? 1 : 0);
        } else {
            insertIndex = OrganizerSettings.pageStart(pageSizes, targetPage);
        }
        insertIndex = Math.max(0, Math.min(tabs.size(), insertIndex));
        tabs.add(insertIndex, moving);
        if (sourcePage != targetPage) {
            pageSizes.set(targetPage, pageSizes.get(targetPage) + 1);
            spillOverflowIntoFollowingPages();
        }

        selectedIndex = tabs.indexOf(moving);
        OrganizerSettings.setLayout(tabs, pageSizes);
        statusMessage = Component.translatable("screen.taborganizer.move_done").getString();
        statusIsError = false;
        updatePageEditor(true);
        ensureSelectionVisible();
    }

    private void moveTabToHeap(int sourceIndex) {
        if (tabs.size() <= 1) {
            statusMessage = "У Heap має залишатися хоча б одна вкладка у списку.";
            statusIsError = true;
            return;
        }
        int sourcePage = OrganizerSettings.getPageIndexForTabIndex(sourceIndex, pageSizes);
        if (sourcePage < 0) return;
        saveCurrentPageTitle();
        CreativeModeTab moving = tabs.remove(sourceIndex);
        heapTabs.add(moving);

        int newSize = pageSizes.get(sourcePage) - 1;
        if (newSize <= 0) {
            pageSizes.remove(sourcePage);
            OrganizerSettings.removePageAndShiftNames(sourcePage);
            editingPageIndex = -1;
        } else {
            pageSizes.set(sourcePage, newSize);
        }

        selectedIndex = Math.min(sourceIndex, Math.max(0, tabs.size() - 1));
        OrganizerSettings.setLayout(tabs, pageSizes);
        updatePageEditor(true);
        ensureSelectionVisible();
        heapScrollOffset = Math.max(0, heapTabs.size() - VISIBLE_ROWS);
        statusMessage = "Вкладку переміщено в Heap.";
        statusIsError = false;
    }

    private void moveHeapTabToPage(int sourceHeapIndex, int targetPage, int targetIndex, boolean after) {
        if (sourceHeapIndex < 0 || sourceHeapIndex >= heapTabs.size()) return;
        if (targetPage < 0 || targetPage >= pageSizes.size()) return;

        CreativeModeTab moving = heapTabs.get(sourceHeapIndex);
        CreativeModeTab targetTab = targetIndex >= 0 && targetIndex < tabs.size() ? tabs.get(targetIndex) : null;
        int insertIndex;
        if (targetTab != null) {
            int currentTargetIndex = tabs.indexOf(targetTab);
            if (currentTargetIndex < 0) return;
            insertIndex = currentTargetIndex + (after ? 1 : 0);
        } else {
            insertIndex = OrganizerSettings.pageStart(pageSizes, targetPage);
        }

        tabs.add(Math.max(0, Math.min(tabs.size(), insertIndex)), moving);
        heapTabs.remove(sourceHeapIndex);
        pageSizes.set(targetPage, pageSizes.get(targetPage) + 1);
        spillOverflowIntoFollowingPages();
        selectedIndex = tabs.indexOf(moving);
        OrganizerSettings.setLayout(tabs, pageSizes);
        updatePageEditor(true);
        ensureSelectionVisible();
        heapScrollOffset = Math.min(heapScrollOffset, Math.max(0, heapTabs.size() - VISIBLE_ROWS));
        statusMessage = "Вкладку повернуто на сторінку.";
        statusIsError = false;
    }

    private void spillOverflowIntoFollowingPages() {
        for (int page = 0; page < pageSizes.size(); page++) {
            int size = pageSizes.get(page);
            if (size > OrganizerSettings.MAX_TABS_PER_PAGE) {
                int overflow = size - OrganizerSettings.MAX_TABS_PER_PAGE;
                pageSizes.set(page, OrganizerSettings.MAX_TABS_PER_PAGE);
                if (page + 1 < pageSizes.size()) {
                    pageSizes.set(page + 1, pageSizes.get(page + 1) + overflow);
                } else {
                    pageSizes.add(overflow);
                }
            }
        }
    }

    @Override
    public boolean mouseScrolled(double mouseX, double mouseY, double scrollX, double scrollY) {
        int delta = (int) Math.signum(scrollY) * 2;
        if (isInsideHeap(mouseX, mouseY)) {
            int maxOffset = Math.max(0, heapTabs.size() - VISIBLE_ROWS);
            heapScrollOffset = Math.max(0, Math.min(maxOffset, heapScrollOffset - delta));
            return true;
        }
        if (isInsideTabList(mouseX, mouseY)) {
            int maxOffset = Math.max(0, buildListEntries().size() - VISIBLE_ROWS);
            scrollOffset = Math.max(0, Math.min(maxOffset, scrollOffset - delta));
            return true;
        }
        return super.mouseScrolled(mouseX, mouseY, scrollX, scrollY);
    }

    private int rowIndexAt(double mouseY) {
        return scrollOffset + (int) ((mouseY - listTop()) / ROW_HEIGHT);
    }

    private int heapRowIndexAt(double mouseY) {
        return heapScrollOffset + (int) ((mouseY - listTop()) / ROW_HEIGHT);
    }

    private void ensureSelectionVisible() {
        List<ListEntry> entries = buildListEntries();
        int selectedRow = -1;
        for (int i = 0; i < entries.size(); i++) {
            if (!entries.get(i).header && entries.get(i).tabIndex == selectedIndex) {
                selectedRow = i;
                break;
            }
        }
        if (selectedRow < 0) return;
        if (selectedRow < scrollOffset) scrollOffset = selectedRow;
        if (selectedRow >= scrollOffset + VISIBLE_ROWS) scrollOffset = selectedRow - VISIBLE_ROWS + 1;
        scrollOffset = Math.max(0, Math.min(Math.max(0, entries.size() - VISIBLE_ROWS), scrollOffset));
    }

    private int listTop() {
        return panelY + 47;
    }

    private boolean isInsideTabList(double mouseX, double mouseY) {
        int listX = panelX + LIST_X_OFFSET;
        return mouseX >= listX && mouseX < listX + LIST_WIDTH
                && mouseY >= listTop() && mouseY < listTop() + VISIBLE_ROWS * ROW_HEIGHT;
    }

    private boolean isInsideHeap(double mouseX, double mouseY) {
        int heapX = panelX + 12;
        return mouseX >= heapX && mouseX < heapX + HEAP_WIDTH
                && mouseY >= listTop() && mouseY < listTop() + VISIBLE_ROWS * ROW_HEIGHT;
    }

    @Override
    public void renderBackground(GuiGraphics graphics, int mouseX, int mouseY, float partialTick) {
        graphics.fill(0, 0, this.width, this.height, 0x88000000);
    }

    @Override
    protected void renderBlurredBackground(float partialTick) {
        // Intentionally disabled for this editor.
    }

    @Override
    public void onClose() {
        if (!heapTabs.isEmpty()) {
            setHeapReturnWarning();
            return;
        }
        saveCurrentPageTitle();
        OrganizerSettings.setLayout(tabs, pageSizes);
        OrganizerSettings.save();

        Minecraft minecraft = Minecraft.getInstance();
        if (parentScreen instanceof CreativeModeInventoryScreen oldScreen && minecraft.player != null) {
            ClientPacketListener connection = minecraft.player.connection;
            FeatureFlagSet enabledFeatures = ((ClientPacketListenerAccessor) (Object) connection)
                    .taborganizer$getEnabledFeatures();
            boolean showOperatorTab = ((CreativeModeInventoryScreenAccessor) (Object) oldScreen)
                    .taborganizer$getDisplayOperatorCreativeTab();
            minecraft.setScreen(new CreativeModeInventoryScreen(minecraft.player, enabledFeatures, showOperatorTab));
        } else {
            minecraft.setScreen(parentScreen);
        }
    }

    @Override
    public boolean isPauseScreen() {
        return false;
    }
}
'''
(BASE / "client/gui/OrganizerScreen.java").write_text(screen_source)

events = BASE / "client/ClientGameEvents.java"
event_source = events.read_text()
event_source = event_source.replace(
    '            if (minecraft.screen == null || minecraft.screen instanceof CreativeModeInventoryScreen) {',
    '            boolean creativeMode = minecraft.player != null && minecraft.player.getAbilities().instabuild;\n'
    '            if (creativeMode && (minecraft.screen == null || minecraft.screen instanceof CreativeModeInventoryScreen)) {'
)
events.write_text(event_source)

mixin = BASE / "mixin/CreativeModeInventoryScreenMixin.java"
mixin_source = mixin.read_text()
if "import net.minecraft.ChatFormatting;" not in mixin_source:
    mixin_source = mixin_source.replace(
        "import net.minecraft.client.gui.GuiGraphics;",
        "import net.minecraft.ChatFormatting;\nimport net.minecraft.client.gui.GuiGraphics;"
    )
if "import com.example.taborganizer.mixin.accessor.AbstractContainerScreenAccessor;" not in mixin_source:
    mixin_source = mixin_source.replace(
        "import com.example.taborganizer.mixin.accessor.CreativeModeInventoryScreenAccessor;",
        "import com.example.taborganizer.mixin.accessor.CreativeModeInventoryScreenAccessor;\n"
        "import com.example.taborganizer.mixin.accessor.AbstractContainerScreenAccessor;"
    )

heading = r'''    @Inject(method = "renderLabels", at = @At("TAIL"), remap = false)
    private void taborganizer$renderPageHeading(GuiGraphics graphics, int mouseX, int mouseY, CallbackInfo ci) {
        CreativeModeTab selected = CreativeModeInventoryScreenAccessor.taborganizer$getSelectedTab();
        int pageIndex = OrganizerSettings.getPageIndex(selected);
        if (pageIndex < 0) return;

        String title = OrganizerSettings.getPageName(pageIndex);
        if (title.isBlank()) return;

        var font = net.minecraft.client.Minecraft.getInstance().font;
        AbstractContainerScreenAccessor screen = (AbstractContainerScreenAccessor) (Object) this;
        int maxTextWidth = screen.taborganizer$getImageWidth() - 44;
        String prefix = "Сторінка " + (pageIndex + 1) + ": ";
        String visibleTitle = title;
        while (visibleTitle.length() > 1 && font.width(prefix) + font.width(visibleTitle) > maxTextWidth) {
            visibleTitle = visibleTitle.substring(0, visibleTitle.length() - 1);
        }
        if (!visibleTitle.equals(title)) visibleTitle += "…";

        Component heading = Component.literal(prefix).withStyle(ChatFormatting.GRAY)
                .append(Component.literal(visibleTitle).withStyle(ChatFormatting.GOLD));
        int boxWidth = font.width(prefix) + font.width(visibleTitle) + 16;
        int boxX = (screen.taborganizer$getImageWidth() - boxWidth) / 2;
        int boxY = -70;

        graphics.fill(boxX, boxY, boxX + boxWidth, boxY + 20, 0xE623201A);
        graphics.renderOutline(boxX, boxY, boxWidth, 20, 0xFF98702C);
        graphics.drawString(font, heading, boxX + 8, boxY + 6, 0xFFFFFFFF, false);
    }
'''
pattern = re.compile(r'    @Inject\(method = "renderLabels".*?private void taborganizer\$renderPageHeading\(.*?\n    }\n', re.S)
mixin_source, count = pattern.subn(heading, mixin_source, count=1)
if count != 1:
    raise SystemExit("Could not replace creative inventory page heading renderer")
mixin.write_text(mixin_source)

# Bump metadata version used by the NeoForge build.
props = ROOT / "gradle.properties"
property_text = props.read_text()
property_text, changed = re.subn(r"(?m)^mod_version=.*$", "mod_version=1.0.4", property_text, count=1)
if changed != 1:
    raise SystemExit("Could not update mod_version in gradle.properties")
props.write_text(property_text)

toml = ROOT / "src/main/resources/META-INF/neoforge.mods.toml"
if toml.exists():
    toml_text = toml.read_text()
    toml_text = toml_text.replace('version="1.0.3"', 'version="1.0.4"')
    toml.write_text(toml_text)

print("Applied beta 1.0.4: styled in-game page heading, scrollable heap staging area, and creative-mode-only editor access.")
