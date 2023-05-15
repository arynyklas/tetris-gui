from PyQt5.QtCore import Qt, QBasicTimer, pyqtBoundSignal, pyqtSignal, QRect, QTimerEvent, QSize, QObject
from PyQt5.QtGui import QPainter, QColor, QKeyEvent, QPaintEvent, QIcon, QFontDatabase, QFont, QClipboard
from PyQt5.QtWidgets import QMainWindow, QFrame, QDesktopWidget, QApplication, QMessageBox
from PyQt5.QtMultimedia import QSound

from pydantic import BaseModel, Field as ModelField
from simplejson import load as load_json, dump as dump_json
from random import randint

from ui import Ui_MainWindow

from typing import List, Tuple


class Assets:
    font: QFont

    class sounds:
        drop: QSound
        line_clear: QSound
        game_over: QSound


class Statuses:
    in_game: str = "In game"
    paused: str = "Paused"
    game_over: str = "Game Over!"


GAME_DATA_FILENAME: str = "data"
GAME_DATA_FILE_ENCODING: str = "utf-8"


class GameData(BaseModel):
    class Config:
        arbitrary_types_allowed: bool = True

    max_points: int = ModelField(default=0)
    last_points: int = ModelField(default=0)

    def save(self) -> None:
        with open(GAME_DATA_FILENAME, "w", encoding=GAME_DATA_FILE_ENCODING) as file:
            dump_json(
                obj = self.dict(),
                fp = file
            )


game_data_raw: dict = {}

try:
    with open(GAME_DATA_FILENAME, "r", encoding=GAME_DATA_FILE_ENCODING) as file:
        game_data_raw = load_json(
            fp = file
        )

except FileNotFoundError:
    pass


game_data: GameData = GameData(
    **game_data_raw
)


class MainWindow(QMainWindow):
    def __init__(self, clipboard: QClipboard):
        super(MainWindow, self).__init__()

        self.ui: Ui_MainWindow = Ui_MainWindow()
        self.ui.setupUi(self)

        self.clipboard: QClipboard = clipboard

        Assets.font = QFont(
            QFontDatabase.applicationFontFamilies(
                QFontDatabase.addApplicationFont("assets/fonts/FiraMono-Medium.ttf")
            )[0]
        )

        Assets.sounds.drop = QSound("assets/sounds/drop.wav", self)
        Assets.sounds.line_clear = QSound("assets/sounds/line_clear.wav", self)
        Assets.sounds.game_over = QSound("assets/sounds/game_over.wav", self)

        for ui_el_name in dir(self.ui):
            if ui_el_name.endswith("LineEdit") or ui_el_name.endswith("Label"):
                getattr(self.ui, ui_el_name).setFont(Assets.font)

        self.game_board: GameBoard = GameBoard(
            frame = self.ui.gameFrame
        )

        self.game_board.status_slot.connect(self.handle_status_signal)
        self.game_board.max_score_slot.connect(self.handle_max_score_signal)
        self.game_board.last_score_slot.connect(self.handle_last_score_signal)

        self.ui.pauseButton.setIcon(QIcon("assets/images/pause.png"))
        self.ui.pauseButton.setIconSize(QSize(32, 32))
        self.ui.pauseButton.clicked.connect(self.handler_pause_button_clicked)

        self.ui.restartButton.setIcon(QIcon("assets/images/restart.png"))
        self.ui.restartButton.setIconSize(QSize(32, 32))
        self.ui.restartButton.clicked.connect(self.handler_restart_button_clicked)

        self.ui.shareScoresButton.setIcon(QIcon("assets/images/share_scores.png"))
        self.ui.shareScoresButton.setIconSize(QSize(32, 32))
        self.ui.shareScoresButton.clicked.connect(self.handler_share_scores_button_clicked)

        self.ui.maxScoreLineEdit.setText(str(game_data.max_points))

        self.game_board.start()

        screen: QRect = QDesktopWidget().screenGeometry()
        size: QRect = self.geometry()

        self.move(
            int((screen.width() - size.width()) / 2),
            int((screen.height() - size.height()) / 2)
        )

        self.show()

    def handle_status_signal(self, status_text: str) -> None:
        self.ui.statusLineEdit.setText(status_text)

    def handle_max_score_signal(self, max_score: int) -> None:
        self.ui.maxScoreLineEdit.setText(str(max_score))

    def handle_last_score_signal(self, last_score: int) -> None:
        self.ui.lastScoreLineEdit.setText(str(last_score))

    def handler_pause_button_clicked(self) -> None:
        self.game_board.pause()

    def handler_restart_button_clicked(self) -> None:
        game_data.save()

        self.game_board.start()

    def handler_share_scores_button_clicked(self) -> None:
        max_scores: int = int(self.ui.maxScoreLineEdit.text())
        last_scores: int = int(self.ui.lastScoreLineEdit.text())

        # clipboard: QClipboard = QClipboard()
        self.clipboard.setText(f"Your results in Tetris:\n\nMax score - {max_scores}\nLast score - {last_scores}")

        message_box: QMessageBox = QMessageBox(self)
        message_box.setWindowTitle(self.windowTitle())
        message_box.setText("Results was copied!")
        message_box.exec()


class GameBoard(QObject):
    status_slot: pyqtBoundSignal = pyqtSignal(str)
    max_score_slot: pyqtBoundSignal = pyqtSignal(int)
    last_score_slot: pyqtBoundSignal = pyqtSignal(int)

    BASE_SQUARE_WIDTH: int = 10
    BASE_SQUARE_HEIGHT: int = 22
    SPEED: int = 300

    COLOR_TABLE: List[int] = [
        0x000000,
        0xCC6666,
        0x66CC66,
        0x6666CC,
        0xCCCC66,
        0xCC66CC,
        0x66CCCC,
        0xDAAA00
    ]

    def __init__(self, frame: QFrame) -> None:
        super(GameBoard, self).__init__()

        self.timer: QBasicTimer = QBasicTimer()
        self.is_waiting_after_line: bool = False

        self.current_x: int = 0
        self.current_y: int = 0
        self.num_lines_removed: int = 0
        self.board: List[int] = []

        self.frame: QFrame = frame

        self.is_started: bool = False
        self.is_paused: bool = False

        self.frame.paintEvent = self.paintEvent
        self.frame.keyPressEvent = self.keyPressEvent
        self.frame.timerEvent = self.timerEvent

        self.current_piece: Shape

    def get_shape_at(self, x: int, y: int) -> int:
        return self.board[(y * self.BASE_SQUARE_WIDTH) + x]

    def set_shape_at(self, x: int, y: int, shape: int) -> None:
        self.board[(y * self.BASE_SQUARE_WIDTH) + x] = shape

    def square_width(self) -> int:
        return self.frame.contentsRect().width() // self.BASE_SQUARE_WIDTH

    def square_height(self) -> int:
        return self.frame.contentsRect().height() // self.BASE_SQUARE_HEIGHT

    def start(self) -> None:
        if self.is_paused:
            return

        self.is_started = True
        self.is_paused = False
        self.is_waiting_after_line = False
        self.num_lines_removed = 0

        self.current_x = 0
        self.current_y = 0
        self.board = []

        self.clear_board()

        self.status_slot.emit(Statuses.in_game)
        self.last_score_slot.emit(0)

        self.new_piece()

        if self.timer.isActive():
            self.timer.stop()

        self.timer.start(self.SPEED, self)

    def pause(self) -> None:
        if not self.is_started:
            return

        self.is_paused = not self.is_paused

        if self.is_paused:
            self.timer.stop()
            self.status_slot.emit(Statuses.paused)

        else:
            self.timer.start(self.SPEED, self)
            self.status_slot.emit(Statuses.in_game)

        self.frame.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter: QPainter = QPainter(self.frame)

        rect: QRect = self.frame.contentsRect()

        board_top: int = rect.bottom() - self.BASE_SQUARE_HEIGHT * self.square_height()

        i: int
        j: int

        for i in range(self.BASE_SQUARE_HEIGHT):
            for j in range(self.BASE_SQUARE_WIDTH):
                shape: int = self.get_shape_at(
                    x = j,
                    y = self.BASE_SQUARE_HEIGHT - i - 1
                )

                if shape != Tetrominoe.NoShape:
                    self.draw_square(
                        painter = painter,
                        x = rect.left() + j * self.square_width(),
                        y = board_top + i * self.square_height(),
                        shape = shape
                    )

        if self.current_piece.shape() != Tetrominoe.NoShape:
            for i in range(4):
                self.draw_square(
                    painter = painter,
                    x = rect.left() + (self.current_x + self.current_piece.x(i)) * self.square_width(),
                    y = board_top + (self.BASE_SQUARE_HEIGHT - (self.current_y - self.current_piece.y(i)) - 1) * self.square_height(),
                    shape = self.current_piece.shape()
                )

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if not self.is_started or self.current_piece.shape() == Tetrominoe.NoShape:
            return

        key: int = event.key()

        if key == Qt.Key_P:
            self.pause()
            return

        if self.is_paused:
            return

        elif key == Qt.Key_Left:
            self.try_move(
                new_piece = self.current_piece,
                new_x = self.current_x - 1,
                new_y = self.current_y
            )

        elif key == Qt.Key_Right:
            self.try_move(
                new_piece = self.current_piece,
                new_x = self.current_x + 1,
                new_y = self.current_y
            )

        elif key == Qt.Key_Down:
            self.try_move(
                new_piece = self.current_piece.rotate_right(),
                new_x = self.current_x,
                new_y = self.current_y
            )

        elif key == Qt.Key_Up:
            self.try_move(
                new_piece = self.current_piece.rotate_left(),
                new_x = self.current_x,
                new_y = self.current_y
            )

        elif key == Qt.Key_Space:
            self.drop_down()

        elif key == Qt.Key_D:
            self.one_line_down()

    def timerEvent(self, event: QTimerEvent) -> None:
        if event.timerId() == self.timer.timerId():
            if self.is_waiting_after_line:
                self.is_waiting_after_line = False
                self.new_piece()

            else:
                self.one_line_down()

    def clear_board(self) -> None:
        self.board = [
            Tetrominoe.NoShape
            for _ in range(self.BASE_SQUARE_HEIGHT * self.BASE_SQUARE_WIDTH)
        ]

    def drop_down(self) -> None:
        new_y: int = self.current_y

        while new_y > 0:
            if not self.try_move(
                new_piece = self.current_piece,
                new_x = self.current_x,
                new_y = new_y - 1
            ):
                break

            new_y -= 1

        self.piece_dropped()

    def one_line_down(self) -> None:
        if not self.try_move(
            new_piece = self.current_piece,
            new_x = self.current_x,
            new_y = self.current_y - 1
        ):
            self.piece_dropped()

    def piece_dropped(self) -> None:
        Assets.sounds.drop.play()

        i: int

        for i in range(4):
            self.set_shape_at(
                x = self.current_x + self.current_piece.x(i),
                y = self.current_y - self.current_piece.y(i),
                shape = self.current_piece.shape()
            )

        self.remove_full_lines()

        if self.is_waiting_after_line:
            Assets.sounds.line_clear.play()
        else:
            self.new_piece()

    def remove_full_lines(self) -> bool:
        num_full_lines: int = 0
        rows_to_remove: List[int] = []

        i: int

        for i in range(self.BASE_SQUARE_HEIGHT):
            n: int = 0

            for j in range(self.BASE_SQUARE_WIDTH):
                if not self.get_shape_at(
                    x = j,
                    y = i
                ) == Tetrominoe.NoShape:
                    n += 1

            if n == 10:
                rows_to_remove.append(i)

        rows_to_remove.reverse()

        i: int
        x: int
        y: int

        for i in rows_to_remove:
            for x in range(i, self.BASE_SQUARE_HEIGHT):
                for y in range(self.BASE_SQUARE_WIDTH):
                    self.set_shape_at(
                        x = x,
                        y = y,
                        shape = self.get_shape_at(
                            x = x,
                            y = y + 1
                        )
                    )

        num_full_lines += len(rows_to_remove)

        if num_full_lines > 0:
            self.num_lines_removed += num_full_lines
            self.last_score_slot.emit(self.num_lines_removed)
            self.is_waiting_after_line = True
            self.current_piece.set_shape(Tetrominoe.NoShape)
            self.frame.update()

    def save_points(self) -> None:
        last_points: int = self.num_lines_removed

        game_data.last_points = last_points
        self.last_score_slot.emit(last_points)

        if game_data.last_points > game_data.max_points:
            game_data.max_points = last_points
            self.max_score_slot.emit(last_points)

        game_data.save()

    def new_piece(self) -> None:
        self.current_piece: Shape = Shape()
        self.current_piece.set_random_shape()
        self.current_x: int = self.BASE_SQUARE_WIDTH // 2 + 1
        self.current_y: int = self.BASE_SQUARE_HEIGHT - 1 + self.current_piece.min_y()

        if not self.try_move(
            new_piece = self.current_piece,
            new_x = self.current_x,
            new_y = self.current_y
        ):
            self.current_piece.set_shape(
                shape = Tetrominoe.NoShape
            )

            self.save_points()

            # NOTE: print board code:
            # print(self.board, "\n")
            # def chunker(items: list, n: int) -> List[list]:
            #     return [
            #         items[i:i + n]
            #         for i in range(0, len(items), n)
            #     ]
            # for row in chunker(self.board, self.BASE_SQUARE_WIDTH)[::-1]:
            #     print(*row, sep=" | ")

            self.timer.stop()
            self.is_started = False

            self.status_slot.emit(Statuses.game_over)

            Assets.sounds.game_over.play()

    def try_move(self, new_piece: 'Shape', new_x: int, new_y: int) -> bool:
        i: int

        for i in range(4):
            x: int = new_x + new_piece.x(i)
            y: int = new_y - new_piece.y(i)

            if x < 0 or x >= self.BASE_SQUARE_WIDTH or y < 0 or y >= self.BASE_SQUARE_HEIGHT:
                return False

            if self.get_shape_at(
                x = x,
                y = y
            ) != Tetrominoe.NoShape:
                return False

        self.current_piece = new_piece
        self.current_x = new_x
        self.current_y = new_y

        self.frame.update()

        return True

    def draw_square(self, painter: QPainter, x: int, y: int, shape: int) -> None:
        color: QColor = QColor(self.COLOR_TABLE[shape])

        square_width: int = self.square_width()
        square_height: int = self.square_height()

        painter.fillRect(
            x + 1,
            y + 1,
            square_width - 2,
            square_height - 2,
            color
        )

        painter.setPen(
            color.lighter()
        )

        painter.drawLine(
            x,
            y + square_height - 1,
            x,
            y
        )

        painter.drawLine(
            x,
            y,
            x + square_width - 1,
            y
        )

        painter.setPen(
            color.darker()
        )

        painter.drawLine(
            x + 1,
            y + square_height - 1,
            x + square_width - 1,
            y + square_height - 1
        )

        painter.drawLine(
            x + square_width - 1,
            y + square_height - 1,
            x + square_width - 1,
            y + 1
        )


class Tetrominoe:
    NoShape: int = 0
    ZShape: int = 1
    SShape: int = 2
    LineShape: int = 3
    TShape: int = 4
    SquareShape: int = 5
    LShape: int = 6
    MirroredLShape: int = 7


class Shape:
    coords_table: List[List[Tuple[int, int]]] = (
        ((0, 0), (0, 0), (0, 0), (0, 0)),
        ((0, -1), (0, 0), (-1, 0), (-1, 1)),
        ((0, -1), (0, 0), (1, 0), (1, 1)),
        ((0, -1), (0, 0), (0, 1), (0, 2)),
        ((-1, 0), (0, 0), (1, 0), (0, 1)),
        ((0, 0), (1, 0), (0, 1), (1, 1)),
        ((-1, -1), (0, -1), (0, 0), (0, 1)),
        ((1, -1), (0, -1), (0, 0), (0, 1))
    )

    def __init__(self) -> None:
        self.coords: List[Tuple[int, int]] = [
            [0, 0]
            for _ in range(4)
        ]

        self.set_shape(
            shape = Tetrominoe.NoShape
        )

    def shape(self) -> int:
        return self.piece_shape

    def set_shape(self, shape: int) -> None:
        table: List[Tuple[int, int]] = self.coords_table[shape]

        for i in range(4):
            for j in range(2):
                self.coords[i][j] = table[i][j]

        self.piece_shape = shape

    def set_random_shape(self) -> None:
        self.set_shape(
            shape = randint(1, len(GameBoard.COLOR_TABLE) - 1)
        )

    def x(self, index: int) -> int:
        return self.coords[index][0]

    def y(self, index: int) -> int:
        return self.coords[index][1]

    def set_x(self, index: int, x: int) -> None:
        self.coords[index][0] = x

    def set_y(self, index: int, y: int) -> None:
        self.coords[index][1] = y

    def min_x(self) -> int:
        value: int = self.coords[0][0]

        for i in range(4):
            value = min(value, self.coords[i][0])

        return value

    def max_x(self) -> int:
        value = self.coords[0][0]

        for i in range(4):
            value = max(value, self.coords[i][0])

        return value

    def min_y(self) -> int:
        value = self.coords[0][1]

        for i in range(4):
            value = min(value, self.coords[i][1])

        return value

    def max_y(self) -> int:
        value = self.coords[0][1]

        for i in range(4):
            value = max(value, self.coords[i][1])

        return value

    def rotate_left(self) -> 'Shape':
        if self.piece_shape == Tetrominoe.SquareShape:
            return self

        result: Shape = Shape()
        result.piece_shape = self.piece_shape

        for i in range(4):
            result.set_x(
                index = i,
                x = self.y(
                    index = i
                )
            )

            result.set_y(
                index = i,
                y = -self.x(
                    index = i
                )
            )

        return result

    def rotate_right(self) -> 'Shape':
        if self.piece_shape == Tetrominoe.SquareShape:
            return self

        result: Shape = Shape()
        result.piece_shape = self.piece_shape

        for i in range(4):
            result.set_x(i, -self.y(i))
            result.set_y(i, self.x(i))

        return result


def main():
    app: QApplication = QApplication([])

    main_window: MainWindow = MainWindow(
        clipboard = app.clipboard()
    )

    app.exec_()

    main_window.game_board.save_points()


if __name__ == "__main__":
    main()
