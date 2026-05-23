"""
타임캐릭터 - 순수 AppKit NSPanel 기반
"""
import sys
import queue
import signal
import shutil
import copy
from pathlib import Path

import objc
from Foundation import NSObject, NSTimer, NSMakeRect, NSMakePoint
import AppKit
from Quartz import CGWindowLevelForKey, kCGMaximumWindowLevelKey

import config as cfg
from tracker import TimeTracker
from browser_watcher import BrowserWatcher

MAX_LEVEL = CGWindowLevelForKey(kCGMaximumWindowLevelKey)


# ── 드래그 가능한 커스텀 뷰 ──────────────────────────────────────────────────

class DraggableView(AppKit.NSView):

    def initWithFrame_controller_(self, frame, controller):
        self = objc.super(DraggableView, self).initWithFrame_(frame)
        if self is None:
            return None
        self._ctrl = controller
        self._drag_start = None
        return self

    def mouseDown_(self, event):
        self._drag_start = event.locationInWindow()
    mouseDown_ = objc.selector(mouseDown_, signature=b"v@:@")

    def mouseDragged_(self, event):
        if self._drag_start is None:
            return
        loc = event.locationInWindow()
        frame = self.window().frame()
        new_x = frame.origin.x + loc.x - self._drag_start.x
        new_y = frame.origin.y + loc.y - self._drag_start.y
        self.window().setFrameOrigin_(NSMakePoint(new_x, new_y))
        bubble = self._ctrl._bubble_panel
        if bubble:
            bubble.setFrameOrigin_(NSMakePoint(
                new_x - 15,
                new_y + frame.size.height + 8,
            ))
    mouseDragged_ = objc.selector(mouseDragged_, signature=b"v@:@")

    def mouseUp_(self, event):
        self._drag_start = None
    mouseUp_ = objc.selector(mouseUp_, signature=b"v@:@")

    def rightMouseDown_(self, event):
        menu = AppKit.NSMenu.alloc().initWithTitle_("")
        s = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "설정", "showSettings:", "")
        s.setTarget_(self._ctrl)
        menu.addItem_(s)
        menu.addItem_(AppKit.NSMenuItem.separatorItem())
        q = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "종료", "quitApp:", "")
        q.setTarget_(self._ctrl)
        menu.addItem_(q)
        AppKit.NSMenu.popUpContextMenu_withEvent_forView_(menu, event, self)
    rightMouseDown_ = objc.selector(rightMouseDown_, signature=b"v@:@")

    def acceptsFirstMouse_(self, event):
        return True
    acceptsFirstMouse_ = objc.selector(acceptsFirstMouse_, signature=b"B@:@")


# ── 사이트 테이블 데이터소스 ─────────────────────────────────────────────────

class SiteDataSource(NSObject):

    def initWithSites_(self, sites):
        self = objc.super(SiteDataSource, self).init()
        if self is None:
            return None
        self.sites = sites
        return self

    def numberOfRowsInTableView_(self, tv):
        return len(self.sites)
    numberOfRowsInTableView_ = objc.selector(
        numberOfRowsInTableView_, signature=b"l@:@")

    def tableView_objectValueForTableColumn_row_(self, tv, col, row):
        s = self.sites[row]
        ident = str(col.identifier())
        if ident == "domain":
            return s.get("domain", "")
        if ident == "message":
            return s.get("message", "")
        if ident == "delay":
            return str(s.get("delay_minutes", 20))
        return ""
    tableView_objectValueForTableColumn_row_ = objc.selector(
        tableView_objectValueForTableColumn_row_, signature=b"@@:@@l")


# ── 사이트 추가 다이얼로그 ───────────────────────────────────────────────────

class AddSiteDialog(NSObject):

    def initWithParent_callback_(self, parent_panel, callback):
        self = objc.super(AddSiteDialog, self).init()
        if self is None:
            return None
        self._parent = parent_panel
        self._callback = callback
        self._panel = None
        self._domain_field = None
        self._message_field = None
        self._delay_field = None
        self._build()
        return self

    @objc.python_method
    def _build(self):
        w, h = 360, 220
        screen = AppKit.NSScreen.mainScreen().frame()
        panel = AppKit.NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(
                (screen.size.width - w) / 2,
                (screen.size.height - h) / 2,
                w, h
            ),
            AppKit.NSWindowStyleMaskTitled | AppKit.NSWindowStyleMaskClosable,
            AppKit.NSBackingStoreBuffered, False,
        )
        panel.setTitle_("사이트 추가")
        panel.setLevel_(MAX_LEVEL)
        c = panel.contentView()

        self._add_label(c, "사이트 도메인", NSMakeRect(20, 168, 120, 22))
        self._domain_field = AppKit.NSTextField.alloc().initWithFrame_(
            NSMakeRect(150, 165, 185, 26))
        self._domain_field.setPlaceholderString_("예: naver.com")
        c.addSubview_(self._domain_field)

        self._add_label(c, "알림 메시지", NSMakeRect(20, 128, 120, 22))
        self._message_field = AppKit.NSTextField.alloc().initWithFrame_(
            NSMakeRect(150, 125, 185, 26))
        self._message_field.setPlaceholderString_("예: 네이버 보고 있어? 😅")
        c.addSubview_(self._message_field)

        self._add_label(c, "알림 시간 (분)", NSMakeRect(20, 88, 120, 22))
        self._delay_field = AppKit.NSTextField.alloc().initWithFrame_(
            NSMakeRect(150, 85, 185, 26))
        self._delay_field.setStringValue_("20")
        c.addSubview_(self._delay_field)

        cancel_btn = AppKit.NSButton.alloc().initWithFrame_(
            NSMakeRect(80, 20, 90, 32))
        cancel_btn.setTitle_("취소")
        cancel_btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
        cancel_btn.setTarget_(self)
        cancel_btn.setAction_("cancel:")
        c.addSubview_(cancel_btn)

        ok_btn = AppKit.NSButton.alloc().initWithFrame_(
            NSMakeRect(185, 20, 90, 32))
        ok_btn.setTitle_("추가")
        ok_btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
        ok_btn.setKeyEquivalent_("\r")
        ok_btn.setTarget_(self)
        ok_btn.setAction_("confirm:")
        c.addSubview_(ok_btn)

        self._panel = panel

    @objc.python_method
    def _add_label(self, parent, text, frame):
        label = AppKit.NSTextField.alloc().initWithFrame_(frame)
        label.setStringValue_(text)
        label.setBezeled_(False)
        label.setDrawsBackground_(False)
        label.setEditable_(False)
        label.setAlignment_(AppKit.NSTextAlignmentRight)
        parent.addSubview_(label)

    @objc.python_method
    def show(self):
        self._domain_field.setStringValue_("")
        self._message_field.setStringValue_("")
        self._delay_field.setStringValue_("20")
        AppKit.NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        self._panel.makeKeyAndOrderFront_(None)

    def confirm_(self, sender):
        domain = str(self._domain_field.stringValue()).strip()
        message = str(self._message_field.stringValue()).strip()
        try:
            delay = int(str(self._delay_field.stringValue()))
        except ValueError:
            delay = 20
        if domain:
            if not message:
                message = f"{domain} 열려 있어! 😅\n슬슬 다른 거 할까?"
            self._callback({
                "domain": domain,
                "message": message,
                "delay_minutes": delay,
            })
        self._panel.orderOut_(None)
    confirm_ = objc.selector(confirm_, signature=b"v@:@")

    def cancel_(self, sender):
        self._panel.orderOut_(None)
    cancel_ = objc.selector(cancel_, signature=b"v@:@")


# ── 설정 창 ──────────────────────────────────────────────────────────────────

class SettingsController(NSObject):

    def initWithOverlay_(self, overlay):
        self = objc.super(SettingsController, self).init()
        if self is None:
            return None
        self._overlay = overlay
        self._panel = None
        self._img_preview = None
        self._rate_field = None
        self._bubble_sec_field = None
        self._table = None
        self._data_source = None
        self._pending_char = None
        self._add_dialog = None
        return self

    @objc.python_method
    def show(self):
        if self._panel is None:
            self._build()
        self._refresh()
        AppKit.NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        self._panel.makeKeyAndOrderFront_(None)

    @objc.python_method
    def _build(self):
        w, h = 420, 560
        screen = AppKit.NSScreen.mainScreen().frame()
        panel = AppKit.NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect((screen.size.width - w) / 2,
                       (screen.size.height - h) / 2, w, h),
            AppKit.NSWindowStyleMaskTitled | AppKit.NSWindowStyleMaskClosable,
            AppKit.NSBackingStoreBuffered, False,
        )
        panel.setTitle_("타임캐릭터 설정")
        panel.setLevel_(MAX_LEVEL)
        c = panel.contentView()

        # ── 캐릭터 섹션 ──
        self._img_preview = AppKit.NSImageView.alloc().initWithFrame_(
            NSMakeRect(w/2 - 60, 450, 120, 90))
        self._img_preview.setImageScaling_(
            AppKit.NSImageScaleProportionallyUpOrDown)
        self._img_preview.setWantsLayer_(True)
        self._img_preview.layer().setCornerRadius_(14.0)
        self._img_preview.layer().setMasksToBounds_(True)
        c.addSubview_(self._img_preview)

        char_btn = AppKit.NSButton.alloc().initWithFrame_(
            NSMakeRect(w/2 - 60, 415, 120, 28))
        char_btn.setTitle_("캐릭터 변경")
        char_btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
        char_btn.setTarget_(self)
        char_btn.setAction_("changeCharacter:")
        c.addSubview_(char_btn)

        # ── 시급 ──
        self._add_label(c, "시급 (원)", NSMakeRect(20, 378, 110, 22))
        self._rate_field = AppKit.NSTextField.alloc().initWithFrame_(
            NSMakeRect(140, 375, 160, 26))
        c.addSubview_(self._rate_field)

        # ── 말풍선 표시 시간 ──
        self._add_label(c, "말풍선 시간 (초)", NSMakeRect(20, 344, 110, 22))
        self._bubble_sec_field = AppKit.NSTextField.alloc().initWithFrame_(
            NSMakeRect(140, 341, 80, 26))
        c.addSubview_(self._bubble_sec_field)

        line1 = AppKit.NSBox.alloc().initWithFrame_(NSMakeRect(15, 322, w-30, 1))
        line1.setBoxType_(AppKit.NSBoxSeparator)
        c.addSubview_(line1)

        # ── 사이트 섹션 레이블 ──
        section = AppKit.NSTextField.alloc().initWithFrame_(
            NSMakeRect(15, 298, 200, 20))
        section.setStringValue_("모니터링 사이트")
        section.setBezeled_(False)
        section.setDrawsBackground_(False)
        section.setEditable_(False)
        section.setFont_(AppKit.NSFont.boldSystemFontOfSize_(12))
        c.addSubview_(section)

        # ── 테이블 ──
        self._data_source = SiteDataSource.alloc().initWithSites_([])
        self._table = AppKit.NSTableView.alloc().initWithFrame_(
            NSMakeRect(0, 0, w - 30, 280))

        for ident, title, width in [
            ("domain",  "사이트",    130),
            ("message", "메시지",    190),
            ("delay",   "분",        50),
        ]:
            col = AppKit.NSTableColumn.alloc().initWithIdentifier_(ident)
            col.setTitle_(title)
            col.setWidth_(width)
            col.setEditable_(False)
            self._table.addTableColumn_(col)

        self._table.setDataSource_(self._data_source)
        self._table.setDelegate_(None)
        self._table.setRowHeight_(22)
        self._table.setUsesAlternatingRowBackgroundColors_(True)

        scroll = AppKit.NSScrollView.alloc().initWithFrame_(
            NSMakeRect(15, 60, w - 30, 265))
        scroll.setDocumentView_(self._table)
        scroll.setHasVerticalScroller_(True)
        scroll.setBorderType_(AppKit.NSBezelBorder)
        c.addSubview_(scroll)

        # ── 추가 / 삭제 버튼 ──
        add_btn = AppKit.NSButton.alloc().initWithFrame_(
            NSMakeRect(15, 28, 80, 28))
        add_btn.setTitle_("+ 추가")
        add_btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
        add_btn.setTarget_(self)
        add_btn.setAction_("addSite:")
        c.addSubview_(add_btn)

        del_btn = AppKit.NSButton.alloc().initWithFrame_(
            NSMakeRect(105, 28, 80, 28))
        del_btn.setTitle_("− 삭제")
        del_btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
        del_btn.setTarget_(self)
        del_btn.setAction_("removeSite:")
        c.addSubview_(del_btn)

        # ── 말풍선 테스트 버튼 ──
        test_btn = AppKit.NSButton.alloc().initWithFrame_(
            NSMakeRect(195, 28, 90, 28))
        test_btn.setTitle_("말풍선 테스트")
        test_btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
        test_btn.setTarget_(self)
        test_btn.setAction_("testBubble:")
        c.addSubview_(test_btn)

        # ── 저장 버튼 ──
        save_btn = AppKit.NSButton.alloc().initWithFrame_(
            NSMakeRect(w - 115, 28, 100, 28))
        save_btn.setTitle_("저장")
        save_btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
        save_btn.setKeyEquivalent_("\r")
        save_btn.setTarget_(self)
        save_btn.setAction_("saveSettings:")
        c.addSubview_(save_btn)

        self._panel = panel

    @objc.python_method
    def _add_label(self, parent, text, frame):
        label = AppKit.NSTextField.alloc().initWithFrame_(frame)
        label.setStringValue_(text)
        label.setBezeled_(False)
        label.setDrawsBackground_(False)
        label.setEditable_(False)
        label.setAlignment_(AppKit.NSTextAlignmentRight)
        parent.addSubview_(label)

    @objc.python_method
    def _refresh(self):
        c = self._overlay._config
        char_path = c.get("character_path", "")
        image = AppKit.NSImage.alloc().initWithContentsOfFile_(char_path) if char_path else None
        if not image:
            image = AppKit.NSImage.alloc().initWithContentsOfFile_(
                str(Path(__file__).parent / "캐릭터예시.jpg"))
        if image:
            self._img_preview.setImage_(image)
        self._rate_field.setStringValue_(str(c.get("hourly_rate", 10320)))
        self._bubble_sec_field.setStringValue_(str(c.get("bubble_seconds", 8)))
        self._data_source.sites = copy.deepcopy(
            c.get("watch_sites", []))
        self._table.reloadData()
        self._pending_char = None

    def changeCharacter_(self, sender):
        p = AppKit.NSOpenPanel.openPanel()
        p.setAllowedFileTypes_(["png", "jpg", "jpeg", "gif"])
        p.setCanChooseFiles_(True)
        p.setCanChooseDirectories_(False)
        if p.runModal() == AppKit.NSModalResponseOK:
            src = p.URLs()[0].path()
            shutil.copy(src, str(cfg.CHAR_FILE))
            self._pending_char = str(cfg.CHAR_FILE)
            img = AppKit.NSImage.alloc().initWithContentsOfFile_(
                self._pending_char)
            self._img_preview.setImage_(img)
    changeCharacter_ = objc.selector(changeCharacter_, signature=b"v@:@")

    def addSite_(self, sender):
        def on_add(site):
            self._data_source.sites.append(site)
            self._table.reloadData()
        self._add_dialog = AddSiteDialog.alloc().initWithParent_callback_(
            self._panel, on_add)
        self._add_dialog.show()
    addSite_ = objc.selector(addSite_, signature=b"v@:@")

    def removeSite_(self, sender):
        row = self._table.selectedRow()
        if 0 <= row < len(self._data_source.sites):
            del self._data_source.sites[row]
            self._table.reloadData()
    removeSite_ = objc.selector(removeSite_, signature=b"v@:@")

    def testBubble_(self, sender):
        self._overlay._show_bubble("👋 말풍선 테스트!\n잘 보이나요? 😄")
    testBubble_ = objc.selector(testBubble_, signature=b"v@:@")

    def saveSettings_(self, sender):
        c = self._overlay._config.copy()
        try:
            c["hourly_rate"] = int(str(self._rate_field.stringValue()))
            self._overlay._tracker.hourly_rate = c["hourly_rate"]
        except ValueError:
            pass
        try:
            c["bubble_seconds"] = max(1, int(str(self._bubble_sec_field.stringValue())))
        except ValueError:
            pass
        if self._pending_char:
            c["character_path"] = self._pending_char
            self._overlay._reload_character(self._pending_char)
        c["watch_sites"] = copy.deepcopy(self._data_source.sites)
        self._overlay._watcher.update_sites(c["watch_sites"])
        cfg.save(c)
        self._overlay._config = c
        self._panel.orderOut_(None)
    saveSettings_ = objc.selector(saveSettings_, signature=b"v@:@")


# ── 메인 오버레이 컨트롤러 ───────────────────────────────────────────────────

class OverlayController(NSObject):

    @objc.python_method
    @classmethod
    def create(cls, tracker, msg_queue, config, watcher):
        ctrl = cls.alloc().init()
        ctrl._tracker = tracker
        ctrl._msg_queue = msg_queue
        ctrl._config = config
        ctrl._watcher = watcher
        ctrl._panel = None
        ctrl._bubble_panel = None
        ctrl._earnings_label = None
        ctrl._time_label = None
        ctrl._img_view = None
        ctrl._settings = SettingsController.alloc().initWithOverlay_(ctrl)
        ctrl._setup()
        return ctrl

    @objc.python_method
    def _setup(self):
        self._create_panel()
        self._create_ui()
        self._start_timers()

    @objc.python_method
    def _create_panel(self):
        screen = AppKit.NSScreen.mainScreen().frame()
        w, h = 185, 265
        panel = AppKit.NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(screen.size.width - w - 20, 80, w, h),
            AppKit.NSWindowStyleMaskBorderless | AppKit.NSWindowStyleMaskNonactivatingPanel,
            AppKit.NSBackingStoreBuffered, False,
        )
        panel.setLevel_(MAX_LEVEL)
        panel.setCollectionBehavior_(
            AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces |
            AppKit.NSWindowCollectionBehaviorStationary
        )
        panel.setOpaque_(False)
        panel.setBackgroundColor_(AppKit.NSColor.clearColor())
        panel.setHasShadow_(False)
        panel.setFloatingPanel_(True)
        panel.setIgnoresMouseEvents_(False)
        drag_view = DraggableView.alloc().initWithFrame_controller_(
            NSMakeRect(0, 0, w, h), self)
        panel.setContentView_(drag_view)
        panel.orderFrontRegardless()
        self._panel = panel

    @objc.python_method
    def _create_ui(self):
        content = self._panel.contentView()
        w = self._panel.frame().size.width

        self._img_view = AppKit.NSImageView.alloc().initWithFrame_(
            NSMakeRect(12, 100, w - 24, w - 24))
        self._img_view.setImageScaling_(
            AppKit.NSImageScaleProportionallyUpOrDown)
        self._img_view.setEditable_(False)
        self._img_view.setWantsLayer_(True)
        self._img_view.layer().setCornerRadius_(20.0)
        self._img_view.layer().setMasksToBounds_(True)
        self._reload_character(self._config.get("character_path", ""))
        content.addSubview_(self._img_view)

        self._earnings_label = self._make_label(
            NSMakeRect(5, 58, w - 10, 34), 13, True,
            AppKit.NSColor.systemYellowColor())
        self._earnings_label.setStringValue_("💰 0원")
        content.addSubview_(self._earnings_label)

        self._time_label = self._make_label(
            NSMakeRect(5, 25, w - 10, 26), 11, False,
            AppKit.NSColor.secondaryLabelColor())
        self._time_label.setStringValue_("⏱ 00:00:00")
        content.addSubview_(self._time_label)

    @objc.python_method
    def _reload_character(self, path: str):
        image = None
        if path:
            image = AppKit.NSImage.alloc().initWithContentsOfFile_(path)
        # 이미지가 없으면 소스 폴더의 기본 캐릭터로 폴백
        if not image:
            fallback = str(Path(__file__).parent / "캐릭터예시.jpg")
            image = AppKit.NSImage.alloc().initWithContentsOfFile_(fallback)
        if image and self._img_view:
            self._img_view.setImage_(image)

    @objc.python_method
    def _make_label(self, frame, size, bold, color):
        label = AppKit.NSTextField.alloc().initWithFrame_(frame)
        label.setBezeled_(False)
        label.setDrawsBackground_(False)
        label.setEditable_(False)
        label.setSelectable_(False)
        label.setAlignment_(AppKit.NSTextAlignmentCenter)
        label.setFont_(AppKit.NSFont.boldSystemFontOfSize_(size) if bold
                       else AppKit.NSFont.systemFontOfSize_(size))
        label.setTextColor_(color)
        return label

    @objc.python_method
    def _start_timers(self):
        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            1.0, self, "updateDisplay:", None, True)
        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.5, self, "checkMessages:", None, True)

    def updateDisplay_(self, timer):
        self._earnings_label.setStringValue_(
            f"💰 {self._tracker.format_earnings()}")
        self._time_label.setStringValue_(
            f"⏱ {self._tracker.format_time()}")
    updateDisplay_ = objc.selector(updateDisplay_, signature=b"v@:@")

    def checkMessages_(self, timer):
        try:
            self._show_bubble(self._msg_queue.get_nowait())
        except queue.Empty:
            pass
    checkMessages_ = objc.selector(checkMessages_, signature=b"v@:@")

    def showSettings_(self, sender):
        self._settings.show()
    showSettings_ = objc.selector(showSettings_, signature=b"v@:@")

    def quitApp_(self, sender):
        self._tracker.save_session()
        AppKit.NSApplication.sharedApplication().terminate_(None)
    quitApp_ = objc.selector(quitApp_, signature=b"v@:@")

    @objc.python_method
    def _show_bubble(self, text):
        if self._bubble_panel:
            self._bubble_panel.orderOut_(None)
        frame = self._panel.frame()
        bw, bh = 220, 80
        bubble = AppKit.NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(frame.origin.x - 15,
                       frame.origin.y + frame.size.height + 8, bw, bh),
            AppKit.NSWindowStyleMaskBorderless | AppKit.NSWindowStyleMaskNonactivatingPanel,
            AppKit.NSBackingStoreBuffered, False,
        )
        bubble.setLevel_(MAX_LEVEL)
        bubble.setCollectionBehavior_(
            AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces |
            AppKit.NSWindowCollectionBehaviorStationary)
        bubble.setOpaque_(False)
        bubble.setBackgroundColor_(AppKit.NSColor.windowBackgroundColor())
        bubble.setHasShadow_(True)

        label = AppKit.NSTextField.alloc().initWithFrame_(
            NSMakeRect(10, 8, bw - 20, bh - 16))
        label.setBezeled_(False)
        label.setDrawsBackground_(False)
        label.setEditable_(False)
        label.setSelectable_(False)
        label.setAlignment_(AppKit.NSTextAlignmentCenter)
        label.setFont_(AppKit.NSFont.systemFontOfSize_(12))
        label.setTextColor_(AppKit.NSColor.labelColor())
        label.setMaximumNumberOfLines_(0)
        label.cell().setWraps_(True)
        label.setStringValue_(text)

        bubble.contentView().addSubview_(label)
        bubble.orderFrontRegardless()
        self._bubble_panel = bubble
        secs = float(self._config.get("bubble_seconds", 8))
        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            secs, self, "hideBubble:", None, False)

    def hideBubble_(self, timer):
        if self._bubble_panel:
            self._bubble_panel.orderOut_(None)
            self._bubble_panel = None
    hideBubble_ = objc.selector(hideBubble_, signature=b"v@:@")


# ── 실행 ─────────────────────────────────────────────────────────────────────

def main():
    config = cfg.load()
    tracker = TimeTracker(hourly_rate=config["hourly_rate"])
    msg_queue = queue.Queue()

    app = AppKit.NSApplication.sharedApplication()
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)

    watcher = BrowserWatcher(msg_queue, watch_sites=config.get("watch_sites", []))
    watcher.start()

    controller = OverlayController.create(tracker, msg_queue, config, watcher)

    def on_exit(sig, frame):
        tracker.save_session()
        watcher.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, on_exit)
    signal.signal(signal.SIGTERM, on_exit)
    app.run()


if __name__ == "__main__":
    main()
