"""
타임캐릭터 - 시간 & 수익 추적 데스크탑 펫
"""
import sys
import signal
import shutil
from pathlib import Path

import objc
from Foundation import NSObject, NSTimer, NSMakeRect, NSMakePoint
import AppKit
from Quartz import CGWindowLevelForKey, kCGMaximumWindowLevelKey

import config as cfg
from tracker import TimeTracker

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
        self.window().setFrameOrigin_(NSMakePoint(
            frame.origin.x + loc.x - self._drag_start.x,
            frame.origin.y + loc.y - self._drag_start.y,
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
        self._pending_char = None
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
        w, h = 320, 300
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

        # 캐릭터 미리보기
        self._img_preview = AppKit.NSImageView.alloc().initWithFrame_(
            NSMakeRect(w/2 - 55, 170, 110, 90))
        self._img_preview.setImageScaling_(
            AppKit.NSImageScaleProportionallyUpOrDown)
        self._img_preview.setWantsLayer_(True)
        self._img_preview.layer().setCornerRadius_(14.0)
        self._img_preview.layer().setMasksToBounds_(True)
        c.addSubview_(self._img_preview)

        char_btn = AppKit.NSButton.alloc().initWithFrame_(
            NSMakeRect(w/2 - 55, 136, 110, 28))
        char_btn.setTitle_("캐릭터 변경")
        char_btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
        char_btn.setTarget_(self)
        char_btn.setAction_("changeCharacter:")
        c.addSubview_(char_btn)

        line = AppKit.NSBox.alloc().initWithFrame_(NSMakeRect(15, 118, w-30, 1))
        line.setBoxType_(AppKit.NSBoxSeparator)
        c.addSubview_(line)

        # 시급
        rate_label = AppKit.NSTextField.alloc().initWithFrame_(
            NSMakeRect(20, 84, 100, 22))
        rate_label.setStringValue_("시급 (원)")
        rate_label.setBezeled_(False)
        rate_label.setDrawsBackground_(False)
        rate_label.setEditable_(False)
        rate_label.setAlignment_(AppKit.NSTextAlignmentRight)
        c.addSubview_(rate_label)

        self._rate_field = AppKit.NSTextField.alloc().initWithFrame_(
            NSMakeRect(130, 81, 150, 26))
        c.addSubview_(self._rate_field)

        # 저장 버튼
        save_btn = AppKit.NSButton.alloc().initWithFrame_(
            NSMakeRect(w - 115, 20, 100, 32))
        save_btn.setTitle_("저장")
        save_btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
        save_btn.setKeyEquivalent_("\r")
        save_btn.setTarget_(self)
        save_btn.setAction_("saveSettings:")
        c.addSubview_(save_btn)

        self._panel = panel

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
            img = AppKit.NSImage.alloc().initWithContentsOfFile_(self._pending_char)
            self._img_preview.setImage_(img)
    changeCharacter_ = objc.selector(changeCharacter_, signature=b"v@:@")

    def saveSettings_(self, sender):
        c = self._overlay._config.copy()
        try:
            c["hourly_rate"] = int(str(self._rate_field.stringValue()))
            self._overlay._tracker.hourly_rate = c["hourly_rate"]
        except ValueError:
            pass
        if self._pending_char:
            c["character_path"] = self._pending_char
            self._overlay._reload_character(self._pending_char)
        cfg.save(c)
        self._overlay._config = c
        self._panel.orderOut_(None)
    saveSettings_ = objc.selector(saveSettings_, signature=b"v@:@")


# ── 메인 오버레이 컨트롤러 ───────────────────────────────────────────────────

class OverlayController(NSObject):

    @objc.python_method
    @classmethod
    def create(cls, tracker, config):
        ctrl = cls.alloc().init()
        ctrl._tracker = tracker
        ctrl._config = config
        ctrl._panel = None
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
        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            1.0, self, "updateDisplay:", None, True)

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

    def updateDisplay_(self, timer):
        self._earnings_label.setStringValue_(
            f"💰 {self._tracker.format_earnings()}")
        self._time_label.setStringValue_(
            f"⏱ {self._tracker.format_time()}")
    updateDisplay_ = objc.selector(updateDisplay_, signature=b"v@:@")

    def showSettings_(self, sender):
        self._settings.show()
    showSettings_ = objc.selector(showSettings_, signature=b"v@:@")

    def quitApp_(self, sender):
        self._tracker.save_session()
        AppKit.NSApplication.sharedApplication().terminate_(None)
    quitApp_ = objc.selector(quitApp_, signature=b"v@:@")


# ── 실행 ─────────────────────────────────────────────────────────────────────

def main():
    config = cfg.load()
    tracker = TimeTracker(hourly_rate=config["hourly_rate"])

    app = AppKit.NSApplication.sharedApplication()
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)

    controller = OverlayController.create(tracker, config)

    def on_exit(sig, frame):
        tracker.save_session()
        sys.exit(0)

    signal.signal(signal.SIGINT, on_exit)
    signal.signal(signal.SIGTERM, on_exit)
    app.run()


if __name__ == "__main__":
    main()
