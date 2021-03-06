# os-specific txt controls

import sys, atexit, ctypes

def init(env):
    if is_windows():
        stdout_handle = ctypes.windll.kernel32.GetStdHandle(ctypes.c_ulong(-11))
        ctypes.windll.kernel32.SetConsoleMode(stdout_handle, 7)
    else: #Unix
        import termios
        fd = sys.stdin.fileno()
        orig = termios.tcgetattr(fd)
        atexit.register(lambda: termios.tcsetattr(fd, termios.TCSAFLUSH, orig))
    def on_exit_common():
        home_cursor()
        cursor_down(env.hdr.screen_height_units)
        reset_color()
        show_cursor()
    atexit.register(on_exit_common)
    hide_cursor()

def reset_color():
    if is_windows():
        stdout_handle = ctypes.windll.kernel32.GetStdHandle(ctypes.c_ulong(-11))
        ctypes.windll.kernel32.SetConsoleTextAttribute(stdout_handle, 7)
    else:
        sys.stdout.write('\x1b[0m')

def write_char_with_color(char, fg_col, bg_col):
    set_color(fg_col, bg_col)
    if char == '\n':
        fill_to_eol_with_bg_color() # insure bg_col covers rest of line
    sys.stdout.write(char)

def write_char_to_bottom_right_corner(char, fg_col, bg_col):

    home_cursor()
    w, h = get_size()
    cursor_down(h-1)
    cursor_right(w-1)

    if is_windows():

        # Windows command line will automatically push buffer down a line
        # on getting the last char of the last line, even without a newline.
        # This breaks any non-scrolling, screen-filling display, and must be
        # worked around.
        #
        # Windows implementing this painful behavior means that anything that
        # fills the screen will see this happen. Right now that's not a problem
        # because xyppy already reserves a 1 char right margin for auto-pause
        # symbols. But if I ever want to allow games to arbitrarily fill the
        # whole screen, I'll have to rework everything to make sure windows
        # doesn't push the screen down in this case, while also making sure not
        # moving the cursor for those instances doesn't impact later text.
        #
        # i.e. that auto-pause status line is totally staying right where it is.

        cbuf = CONSOLE_SCREEN_BUFFER_INFO()
        stdout_handle = ctypes.windll.kernel32.GetStdHandle(ctypes.c_ulong(-11))
        ctypes.windll.kernel32.GetConsoleScreenBufferInfo(stdout_handle, ctypes.byref(cbuf))
        cursor = cbuf.dwCursorPosition

        written = ctypes.c_uint(0)
        ctypes.windll.kernel32.WriteConsoleOutputCharacterA(stdout_handle,
                                                            ctypes.c_char_p(char),
                                                            len(char),
                                                            cursor,
                                                            ctypes.byref(written))
    else:
        sys.stdout.write(char)

class COORD(ctypes.Structure):
    _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]

class SMALL_RECT(ctypes.Structure):
    _fields_ = [("Left", ctypes.c_short), ("Top", ctypes.c_short),
                ("Right", ctypes.c_short), ("Bottom", ctypes.c_short)]

class CONSOLE_SCREEN_BUFFER_INFO(ctypes.Structure):
    _fields_ = [("dwSize", COORD),
                ("dwCursorPosition", COORD),
                ("wAttributes", ctypes.c_ushort),
                ("srWindow", SMALL_RECT),
                ("dwMaximumWindowSize", COORD)]

def get_size():
    if is_windows():
        cbuf = CONSOLE_SCREEN_BUFFER_INFO()
        stdout_handle = ctypes.windll.kernel32.GetStdHandle(ctypes.c_ulong(-11))
        ctypes.windll.kernel32.GetConsoleScreenBufferInfo(stdout_handle, ctypes.byref(cbuf))
        return cbuf.srWindow.Right-cbuf.srWindow.Left+1, cbuf.srWindow.Bottom-cbuf.srWindow.Top+1
    else:
        import fcntl, termios, struct
        result = fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, struct.pack('HHHH', 0, 0, 0, 0))
        h, w, hp, wp = struct.unpack('HHHH', result)
        return w, h

def scroll_down():
    # need to reset color to avoid adding bg at bottom
    sys.stdout.write('\x1b[0m')
    if is_windows():
        cbuf = CONSOLE_SCREEN_BUFFER_INFO()
        stdout_handle = ctypes.windll.kernel32.GetStdHandle(ctypes.c_ulong(-11))
        ctypes.windll.kernel32.GetConsoleScreenBufferInfo(stdout_handle, ctypes.byref(cbuf))
        if cbuf.srWindow.Bottom < cbuf.dwSize.Y - 1:
            cbuf.srWindow.Bottom += 1
            cbuf.srWindow.Top += 1
            ctypes.windll.kernel32.SetConsoleWindowInfo(stdout_handle, 1, ctypes.byref(cbuf.srWindow))
    else:
        sys.stdout.write('\x1b[S')
def fill_to_eol_with_bg_color():
    sys.stdout.write('\x1b[K') # insure bg_col covers rest of line
def cursor_to_left_side():
    sys.stdout.write('\x1b[G')
def cursor_up(count=1):
    sys.stdout.write('\x1b['+str(count)+'A')
def cursor_down(count=1):
    sys.stdout.write('\x1b['+str(count)+'B')
def cursor_right(count=1):
    sys.stdout.write('\x1b['+str(count)+'C')
def cursor_left(count=1):
    sys.stdout.write('\x1b['+str(count)+'D')
def clear_line():
    sys.stdout.write('\x1b[2K')
def hide_cursor():
    sys.stdout.write('\x1b[?25l')
def show_cursor():
    sys.stdout.write('\x1b[?25h')
def clear_screen():
    sys.stdout.write('\x1b[2J')
def home_cursor():
    sys.stdout.write('\x1b[H')

def set_color(fg_col, bg_col):
    # assuming VT100 compat
    color = str(fg_col + 28)
    sys.stdout.write('\x1b['+color+'m')
    color = str(bg_col + 38)
    sys.stdout.write('\x1b['+color+'m')

# TODO: any other encodings to check for?
def supports_unicode():
    return sys.stdout.encoding in ['UTF-8', 'UTF-16', 'UTF-32']

is_windows_cached = None
def is_windows():
    global is_windows_cached
    if is_windows_cached == None:
        try:
            import msvcrt
            is_windows_cached = True
        except ImportError:
            is_windows_cached = False
    return is_windows_cached

def getch():
    if is_windows():
        c = chr(ctypes.cdll.msvcrt._getch())
        if ord(c) == 3:
            # I see this when i hit ctrl-c
            raise KeyboardInterrupt
        return c
    else: #Unix
        import termios, tty
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSAFLUSH, old)
        return ch

def putc(c):
    sys.stdout.write(c)
