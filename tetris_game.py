from PyQt5.QtCore import Qt, QBasicTimer, pyqtSignal, QRect, QTimerEvent
from PyQt5.QtGui import QPainter, QColor, QKeyEvent, QPaintEvent
from PyQt5.QtWidgets import QStatusBar, QMainWindow, QFrame, QWidget, QDesktopWidget, QApplication, QGridLayout

from pydantic import BaseModel, Field as ModelField
from simplejson import load as load_json, dump as dump_json

import random
import sys

from typing import List, Tuple


GAME_DATA_FILENAME: str = "data"
GAME_DATA_FILE_ENCODING: str = "utf-8"


class GameData(BaseModel):
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


class Tetris(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.initUI()

    def initUI(self) -> None:
        self.tboard: Board = Board(self)
        # self.tboard.layout: QGridLayout = QGridLayout()
        self.setCentralWidget(self.tboard)
        # layout.addWidget(self.tboard)

        self.statusbar: QStatusBar = self.statusBar()
        self.tboard.status_bar_signal[str].connect(self.statusbar.showMessage)
        # status_bar: QStatusBar = self.statusBar()
        # self.tboard.status_bar_signal[str].connect(status_bar.showMessage)

        # self.glayout
        # layout: QGridLayout = QGridLayout()
        # self.tboard.layout.addWidget(status_bar, 0, 0)
        # self.setLayout(layout)
        # self.tboard.layout = layout

        self.tboard.start()

        # self.resize(180, 380)
        self.resize(200, 420)

        screen: QRect = QDesktopWidget().screenGeometry()
        size: QRect = self.geometry()

        self.move(
            int((screen.width() - size.width()) / 2),
            int((screen.height() - size.height()) / 2)
        )

        self.setWindowTitle("Game - Tetris")
        self.show()


class Board(QFrame):
    status_bar_signal: pyqtSignal = pyqtSignal(str)

    BASE_WIDTH: int = 10
    BASE_HEIGHT: int = 22
    SPEED: int = 300 # 10 # 300 # TODO: return old value

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

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)

        self.init_board()

    def init_board(self) -> None:
        self.timer: QBasicTimer = QBasicTimer()
        self.is_waiting_after_line: bool = False

        self.current_x: int = 0
        self.current_y: int = 0
        self.num_lines_removed: int = 0
        self.board: List[int] = []

        self.setFocusPolicy(Qt.StrongFocus)

        self.is_started: bool = False
        self.is_paused: bool = False

        self.clear_board()

    def get_shape_at(self, x: int, y: int) -> int:
        return self.board[y * self.BASE_WIDTH + x]

    def set_shape_at(self, x: int, y: int, shape: int) -> None:
        self.board[y * self.BASE_WIDTH + x] = shape

    def square_width(self) -> int:
        return self.contentsRect().width() // self.BASE_WIDTH

    def square_height(self) -> int:
        return self.contentsRect().height() // self.BASE_HEIGHT

    def start(self) -> None:
        if self.is_paused:
            return

        self.is_started = True
        self.is_waiting_after_line = False
        self.num_lines_removed = 0

        self.clear_board()

        self.status_bar_signal.emit(str(self.num_lines_removed))

        self.new_piece()

        self.timer.start(self.SPEED, self)

    def pause(self) -> None:
        if not self.is_started:
            return

        self.is_paused = not self.is_paused

        if self.is_paused:
            self.timer.stop()
            self.status_bar_signal.emit("paused")

        else:
            self.timer.start(self.SPEED, self)
            self.status_bar_signal.emit(str(self.num_lines_removed))

        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter: QPainter = QPainter(self)
        rect: QRect = self.contentsRect()

        boardTop: int = rect.bottom() - self.BASE_HEIGHT * self.square_height()

        i: int
        j: int

        for i in range(self.BASE_HEIGHT):
            for j in range(self.BASE_WIDTH):
                shape: int = self.get_shape_at(
                    x = j,
                    y = self.BASE_HEIGHT - i - 1
                )

                if shape != Tetrominoe.NoShape:
                    self.draw_square(
                        painter = painter,
                        x = rect.left() + j * self.square_width(),
                        y = boardTop + i * self.square_height(),
                        shape = shape
                    )

        if self.current_piece.shape() != Tetrominoe.NoShape:
            for i in range(4):
                self.draw_square(
                    painter = painter,
                    x = rect.left() + (self.current_x + self.current_piece.x(i)) * self.square_width(),
                    y = boardTop + (self.BASE_HEIGHT - (self.current_y - self.current_piece.y(i)) - 1) * self.square_height(),
                    shape = self.current_piece.shape()
                )

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if not self.is_started or self.current_piece.shape() == Tetrominoe.NoShape:
            super(Board, self).keyPressEvent(event)
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

        else:
            super(Board, self).keyPressEvent(event)

    def timerEvent(self, event: QTimerEvent) -> None:
        if event.timerId() == self.timer.timerId():
            if self.is_waiting_after_line:
                self.is_waiting_after_line = False
                self.new_piece()

            else:
                self.one_line_down()

        else:
            super(Board, self).timerEvent(event)

    def clear_board(self) -> None:
        for _ in range(self.BASE_HEIGHT * self.BASE_WIDTH):
            self.board.append(Tetrominoe.NoShape)

    def drop_down(self) -> None:
        new_y: int = self.current_y

        while new_y > 0:
            if not self.try_move(self.current_piece, self.current_x, new_y - 1):
                break

            new_y -= 1

        self.piece_dropped()

    def one_line_down(self) -> None:
        if not self.try_move(self.current_piece, self.current_x, self.current_y - 1):
            self.piece_dropped()

    def piece_dropped(self) -> None:
        i: int

        for i in range(4):
            self.set_shape_at(
                x = self.current_x + self.current_piece.x(i),
                y = self.current_y - self.current_piece.y(i),
                shape = self.current_piece.shape()
            )

        self.remove_full_lines()

        if not self.is_waiting_after_line:
            self.new_piece()

    def remove_full_lines(self) -> None:
        num_full_lines: int = 0
        rows_to_remove: List[int] = []

        i: int

        for i in range(self.BASE_HEIGHT):
            n: int = 0

            for j in range(self.BASE_WIDTH):
                if not self.get_shape_at(
                    x = j,
                    y = i
                ) == Tetrominoe.NoShape:
                    n = n + 1

            if n == 10:
                rows_to_remove.append(i)

        rows_to_remove.reverse()

        m: int
        k: int
        l: int

        for m in rows_to_remove:
            for k in range(m, self.BASE_HEIGHT):
                for l in range(self.BASE_WIDTH):
                    self.set_shape_at(
                        x = l,
                        y = k,
                        shape = self.get_shape_at(
                            x = l,
                            y = k + 1
                        )
                    )

        num_full_lines += len(rows_to_remove)

        if num_full_lines > 0:
            self.num_lines_removed += num_full_lines
            self.status_bar_signal.emit(str(self.num_lines_removed))

            self.is_waiting_after_line = True
            self.current_piece.set_shape(Tetrominoe.NoShape)
            self.update()

    def new_piece(self) -> None:
        self.current_piece: Shape = Shape()
        self.current_piece.setRandomShape()
        self.current_x: int = self.BASE_WIDTH // 2 + 1
        self.current_y: int = self.BASE_HEIGHT - 1 + self.current_piece.minY()

        if not self.try_move(
            new_piece = self.current_piece,
            new_x = self.current_x,
            new_y = self.current_y
        ):
            self.current_piece.set_shape(
                shape = Tetrominoe.NoShape
            )

            game_data.last_points = self.num_lines_removed

            if game_data.last_points > game_data.max_points:
                game_data.max_points = game_data.last_points

            game_data.save()

            # NOTE: print board code:
            # print(self.board, "\n")
            # def chunker(items: list, n: int) -> List[list]:
            #     return [
            #         items[i:i + n]
            #         for i in range(0, len(items), n)
            #     ]
            # for row in chunker(self.board, self.BASE_WIDTH)[::-1]:
            #     print(*row, sep=" | ")

            self.timer.stop()
            self.is_started = False
            self.status_bar_signal.emit("Game over")

    def try_move(self, new_piece: 'Shape', new_x: int, new_y: int) -> bool:
        i: int

        for i in range(4):
            x: int = new_x + new_piece.x(i)
            y: int = new_y - new_piece.y(i)

            if x < 0 or x >= self.BASE_WIDTH or y < 0 or y >= self.BASE_HEIGHT:
                return False

            if self.get_shape_at(
                x = x,
                y = y
            ) != Tetrominoe.NoShape:
                return False

        self.current_piece = new_piece
        self.current_x = new_x
        self.current_y = new_y

        self.update()

        return True

    def draw_square(self, painter: QPainter, x: int, y: int, shape: int) -> None:
        color: QColor = QColor(self.COLOR_TABLE[shape])

        painter.fillRect(
            x + 1,
            y + 1,
            self.square_width() - 2,
            self.square_height() - 2,
            color
        )

        painter.setPen(
            color.lighter()
        )

        painter.drawLine(
            x,
            y + self.square_height() - 1,
            x,
            y
        )

        painter.drawLine(
            x,
            y,
            x + self.square_width() - 1,
            y
        )

        painter.setPen(
            color.darker()
        )

        painter.drawLine(
            x + 1,
            y + self.square_height() - 1,
            x + self.square_width() - 1,
            y + self.square_height() - 1
        )

        painter.drawLine(
            x + self.square_width() - 1,
            y + self.square_height() - 1,
            x + self.square_width() - 1,
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
    coordsTable: List[List[Tuple[int, int]]] = (
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

        # self.piece_shape: int = Tetrominoe.NoShape

        self.set_shape(
            shape = Tetrominoe.NoShape
        )

    def shape(self) -> int:
        return self.piece_shape

    def set_shape(self, shape: int) -> None:
        table: List[Tuple[int, int]] = self.coordsTable[shape]

        for i in range(4):
            for j in range(2):
                self.coords[i][j] = table[i][j]

        self.piece_shape = shape

    def setRandomShape(self) -> None:
        self.set_shape(
            shape = random.randint(1, 7)
        )

    def x(self, index: int) -> int:
        return self.coords[index][0]

    def y(self, index: int) -> int:
        return self.coords[index][1]

    def setX(self, index: int, x: int) -> None:
        self.coords[index][0] = x

    def setY(self, index: int, y: int) -> None:
        self.coords[index][1] = y

    def minX(self) -> int:
        value: int = self.coords[0][0]

        for i in range(4):
            value = min(value, self.coords[i][0])

        return value

    def maxX(self) -> int:
        value = self.coords[0][0]

        for i in range(4):
            value = max(value, self.coords[i][0])

        return value

    def minY(self) -> int:
        value = self.coords[0][1]

        for i in range(4):
            value = min(value, self.coords[i][1])

        return value

    def maxY(self) -> int:
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
            result.setX(
                index = i,
                x = self.y(
                    index = i
                )
            )

            result.setY(
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
            result.setX(i, -self.y(i))
            result.setY(i, self.x(i))

        return result


def main():
    app: QApplication = QApplication(sys.argv)
    game: Tetris = Tetris()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
