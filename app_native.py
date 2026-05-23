"""
타임캐릭터 - 시간 & 수익 추적 데스크탑 펫
"""
import sys
import signal
import shutil
from datetime import date, datetime
from pathlib import Path

import objc
from Foundation import NSObject, NSTimer, NSMakeRect, NSMakePoint, NSMakeSize
import AppKit
from Quartz import CGWindowLevelForKey, kCGMaximumWindowLevelKey

import config as cfg
from tracker import TimeTracker

MAX_LEVEL = CGWindowLevelForKey(kCGMaximumWindowLevelKey)
FEED_INTERVAL = 300  # 5분


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
        share = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "캐릭터 자랑하기 📸", "shareCharacter:", "")
        share.setTarget_(self._ctrl)
        menu.addItem_(share)
        log = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "오늘의 기록 📝", "showLog:", "")
        log.setTarget_(self._ctrl)
        menu.addItem_(log)
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


# ── 일지 창 ──────────────────────────────────────────────────────────────────

class LogController(NSObject):

    def initWithLevel_(self, overlay):
        self = objc.super(LogController, self).init()
        if self is None:
            return None
        self._overlay = overlay
        self._panel = None
        self._input = None
        self._text_view = None
        return self

    @objc.python_method
    def show(self):
        if self._panel is None:
            self._build()
        self._reload()
        AppKit.NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        self._panel.makeKeyAndOrderFront_(None)

    @objc.python_method
    def _build(self):
        w, h = 300, 420
        screen = AppKit.NSScreen.mainScreen().frame()
        panel = AppKit.NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect((screen.size.width - w) / 2,
                       (screen.size.height - h) / 2, w, h),
            AppKit.NSWindowStyleMaskTitled | AppKit.NSWindowStyleMaskClosable,
            AppKit.NSBackingStoreBuffered, False,
        )
        panel.setTitle_(f"오늘의 기록  {date.today()}")
        panel.setLevel_(MAX_LEVEL)
        c = panel.contentView()

        # 입력창
        self._input = AppKit.NSTextField.alloc().initWithFrame_(
            NSMakeRect(12, h - 52, w - 100, 32))
        self._input.setPlaceholderString_("오늘 뭐 했어?")
        self._input.setBezelStyle_(AppKit.NSTextFieldRoundedBezel)
        c.addSubview_(self._input)

        add_btn = AppKit.NSButton.alloc().initWithFrame_(
            NSMakeRect(w - 82, h - 52, 70, 32))
        add_btn.setTitle_("기록")
        add_btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
        add_btn.setKeyEquivalent_("\r")
        add_btn.setTarget_(self)
        add_btn.setAction_("addEntry:")
        c.addSubview_(add_btn)

        line = AppKit.NSBox.alloc().initWithFrame_(NSMakeRect(0, h - 62, w, 1))
        line.setBoxType_(AppKit.NSBoxSeparator)
        c.addSubview_(line)

        # 기록 목록
        self._text_view = AppKit.NSTextView.alloc().initWithFrame_(
            NSMakeRect(0, 0, w, h - 70))
        self._text_view.setEditable_(False)
        self._text_view.setSelectable_(True)
        self._text_view.setFont_(AppKit.NSFont.systemFontOfSize_(13))
        self._text_view.setTextContainerInset_(AppKit.NSMakeSize(8, 8))
        self._text_view.setAutomaticLinkDetectionEnabled_(False)

        scroll = AppKit.NSScrollView.alloc().initWithFrame_(
            NSMakeRect(0, 0, w, h - 70))
        scroll.setDocumentView_(self._text_view)
        scroll.setHasVerticalScroller_(True)
        scroll.setBorderType_(AppKit.NSNoBorder)
        c.addSubview_(scroll)

        self._panel = panel

    @objc.python_method
    def _reload(self):
        today = str(date.today())
        log = cfg.load_log()
        entries = log.get(today, [])
        if entries:
            text = "\n".join(f"[{e['time']}]  {e['text']}" for e in reversed(entries))
        else:
            text = "아직 기록이 없어요. 오늘 뭘 했는지 남겨봐요! 😊"
        self._text_view.setString_(text)

    def addEntry_(self, sender):
        text = str(self._input.stringValue()).strip()
        if not text:
            return
        today = str(date.today())
        now = datetime.now().strftime("%H:%M")
        log = cfg.load_log()
        log.setdefault(today, []).append({"time": now, "text": text})
        cfg.save_log(log)
        self._input.setStringValue_("")
        self._reload()
    addEntry_ = objc.selector(addEntry_, signature=b"v@:@")


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
        ctrl._level = config.get("level", 0)
        ctrl._panel = None
        ctrl._feed_panel = None
        ctrl._earnings_label = None
        ctrl._time_label = None
        ctrl._level_label = None
        ctrl._img_view = None
        ctrl._settings = SettingsController.alloc().initWithOverlay_(ctrl)
        ctrl._log = LogController.alloc().initWithLevel_(ctrl)
        ctrl._setup()
        return ctrl

    @objc.python_method
    def _setup(self):
        self._create_panel()
        self._create_ui()
        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            1.0, self, "updateDisplay:", None, True)
        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            FEED_INTERVAL, self, "showFeedButton:", None, True)

    @objc.python_method
    def _create_panel(self):
        screen = AppKit.NSScreen.mainScreen().frame()
        w, h = 185, 290
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
            NSMakeRect(12, 110, w - 24, w - 24))
        self._img_view.setImageScaling_(
            AppKit.NSImageScaleProportionallyUpOrDown)
        self._img_view.setEditable_(False)
        self._img_view.setWantsLayer_(True)
        self._img_view.layer().setCornerRadius_(20.0)
        self._img_view.layer().setMasksToBounds_(True)
        self._reload_character(self._config.get("character_path", ""))
        content.addSubview_(self._img_view)

        self._earnings_label = self._make_label(
            NSMakeRect(5, 70, w - 10, 34), 13, True,
            AppKit.NSColor.systemYellowColor())
        self._earnings_label.setStringValue_("💰 0원")
        content.addSubview_(self._earnings_label)

        self._time_label = self._make_label(
            NSMakeRect(5, 44, w - 10, 24), 11, False,
            AppKit.NSColor.secondaryLabelColor())
        self._time_label.setStringValue_("⏱ 00:00:00")
        content.addSubview_(self._time_label)

        self._level_label = self._make_label(
            NSMakeRect(5, 14, w - 10, 24), 12, True,
            AppKit.NSColor.systemGreenColor())
        self._level_label.setStringValue_(f"⭐ Lv.{self._level}")
        content.addSubview_(self._level_label)

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

    def showFeedButton_(self, timer):
        if self._feed_panel is not None:
            return
        frame = self._panel.frame()
        bw, bh = 140, 44
        feed = AppKit.NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(frame.origin.x + (frame.size.width - bw) / 2,
                       frame.origin.y - bh - 8, bw, bh),
            AppKit.NSWindowStyleMaskBorderless | AppKit.NSWindowStyleMaskNonactivatingPanel,
            AppKit.NSBackingStoreBuffered, False,
        )
        feed.setLevel_(MAX_LEVEL)
        feed.setCollectionBehavior_(
            AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces |
            AppKit.NSWindowCollectionBehaviorStationary)
        feed.setOpaque_(False)
        feed.setBackgroundColor_(AppKit.NSColor.windowBackgroundColor())
        feed.setHasShadow_(True)

        btn = AppKit.NSButton.alloc().initWithFrame_(NSMakeRect(0, 0, bw, bh))
        btn.setTitle_("🍚 밥주기!")
        btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
        btn.setFont_(AppKit.NSFont.boldSystemFontOfSize_(14))
        btn.setTarget_(self)
        btn.setAction_("feedCharacter:")
        feed.contentView().addSubview_(btn)
        feed.orderFrontRegardless()
        self._feed_panel = feed
    showFeedButton_ = objc.selector(showFeedButton_, signature=b"v@:@")

    def feedCharacter_(self, sender):
        self._level += 1
        self._level_label.setStringValue_(f"⭐ Lv.{self._level}")
        c = self._config.copy()
        c["level"] = self._level
        cfg.save(c)
        self._config = c
        if self._feed_panel:
            self._feed_panel.orderOut_(None)
            self._feed_panel = None
    feedCharacter_ = objc.selector(feedCharacter_, signature=b"v@:@")

    def shareCharacter_(self, sender):
        self._save_share_card()
    shareCharacter_ = objc.selector(shareCharacter_, signature=b"v@:@")

    @objc.python_method
    def _save_share_card(self):
        cw, ch = 400, 520
        image = AppKit.NSImage.alloc().initWithSize_(NSMakeSize(cw, ch))
        image.lockFocus()

        # 배경
        AppKit.NSColor.colorWithRed_green_blue_alpha_(0.08, 0.08, 0.12, 1.0).setFill()
        AppKit.NSRectFill(NSMakeRect(0, 0, cw, ch))

        # 캐릭터 이미지
        char_path = self._config.get("character_path", "")
        char_img = AppKit.NSImage.alloc().initWithContentsOfFile_(char_path) if char_path else None
        if not char_img:
            char_img = AppKit.NSImage.alloc().initWithContentsOfFile_(
                str(Path(__file__).parent / "캐릭터예시.jpg"))
        if char_img:
            char_img.drawInRect_(NSMakeRect(cw/2 - 100, 240, 200, 200))

        def draw_text(text, x, y, size, bold=False, color=None):
            font = (AppKit.NSFont.boldSystemFontOfSize_(size) if bold
                    else AppKit.NSFont.systemFontOfSize_(size))
            attrs = {
                AppKit.NSFontAttributeName: font,
                AppKit.NSForegroundColorAttributeName: (
                    color or AppKit.NSColor.whiteColor()),
            }
            ns = AppKit.NSString.stringWithString_(text)
            ns.drawAtPoint_withAttributes_(NSMakePoint(x, y), attrs)

        # 타이틀
        draw_text("타임캐릭터", cw/2 - 65, 470, 22, bold=True)

        # 구분선
        AppKit.NSColor.colorWithRed_green_blue_alpha_(1, 1, 1, 0.15).setFill()
        AppKit.NSRectFill(NSMakeRect(40, 458, cw - 80, 1))

        # 레벨
        draw_text(f"⭐  Lv.{self._level}", cw/2 - 50, 200, 26, bold=True,
                  color=AppKit.NSColor.colorWithRed_green_blue_alpha_(1.0, 0.85, 0.2, 1.0))

        # 활성 시간
        draw_text("활성 시간", 40, 160, 12,
                  color=AppKit.NSColor.colorWithRed_green_blue_alpha_(0.6, 0.6, 0.6, 1.0))
        draw_text(self._tracker.format_time(), cw/2 - 55, 138, 20, bold=True)

        # 오늘 수익
        draw_text("오늘 번 돈", 40, 108, 12,
                  color=AppKit.NSColor.colorWithRed_green_blue_alpha_(0.6, 0.6, 0.6, 1.0))
        draw_text(self._tracker.format_earnings(), cw/2 - 55, 86, 20, bold=True,
                  color=AppKit.NSColor.colorWithRed_green_blue_alpha_(1.0, 0.85, 0.2, 1.0))

        # 날짜
        draw_text(str(date.today()), cw/2 - 40, 40, 12,
                  color=AppKit.NSColor.colorWithRed_green_blue_alpha_(0.5, 0.5, 0.5, 1.0))

        image.unlockFocus()

        # PNG로 저장
        tiff = image.TIFFRepresentation()
        rep = AppKit.NSBitmapImageRep.imageRepWithData_(tiff)
        png = rep.representationUsingType_properties_(
            AppKit.NSBitmapImageFileTypePNG, {})
        save_path = str(Path.home() / "Desktop" / f"타임캐릭터_{date.today()}.png")
        png.writeToFile_atomically_(save_path, True)

        AppKit.NSWorkspace.sharedWorkspace().openFile_(save_path)

    def showLog_(self, sender):
        self._log.show()
    showLog_ = objc.selector(showLog_, signature=b"v@:@")

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
