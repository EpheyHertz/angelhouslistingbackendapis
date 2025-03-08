import sys
import os
import random
from PyQt6.QtGui import QAction, QColor, QPixmap, QImage, QPainter, QBrush
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QMenuBar, QMenu, QFileDialog, QVBoxLayout, QSplitter, QMessageBox, QInputDialog
)
from PyQt6.QtCore import Qt, QTimer, QPoint
from PIL import Image, ImageOps
import numpy as np
import cv2

class Shape:
    def __init__(self, position, size, color, opacity, shape_type):
        self.position = position
        self.size = size
        self.color = color
        self.opacity = opacity
        self.shape_type = shape_type

class Canvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.image_width = 0
        self.image_height = 0
        self.generated_width = 0  
        self.generated_height = 0
        self.original_pixmap = None
        self.shapes = []
        self.background_color = QColor(255, 255, 255)
        self.generated_background_color = QColor(255, 255, 255)  # Initialize average color
        self.margin = 30
        self.use_rectangles = False
        self.num_shapes = 60000
        self.opacity = 1.0
        self.max_rect_size = 6  # Default maximum rectangle size

    def load_image(self, image_path):
        image = Image.open(image_path).convert("RGB")
        image = ImageOps.exif_transpose(image)
        self.image_width, self.image_height = image.size
        self.generated_width, self.generated_height = self.image_width, self.image_height

        # Compute average color
        np_image = np.array(image)
        avg_color = np.mean(np_image, axis=(0, 1)).astype(int)
        self.generated_background_color = QColor(*avg_color)

        total_width = int(self.image_width * 2.1)
        total_height = max(self.image_height, self.generated_height)
        self.setFixedSize(total_width, total_height)

        self.original_image = image
        self.original_pixmap = QPixmap.fromImage(self.pil2qimage(image))
        self.update()

    def pil2qimage(self, pil_img):
        pil_img = pil_img.convert("RGBA")
        data = pil_img.tobytes("raw", "RGBA")
        return QImage(data, pil_img.size[0], pil_img.size[1], QImage.Format.Format_RGBA8888)

    def add_shape(self, shape):
        self.shapes.append(shape)
        self.update()

    def clear_shapes(self):
        self.shapes.clear()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.background_color)

        if self.original_pixmap:
            painter.drawPixmap(0, 0, self.image_width, self.image_height, self.original_pixmap)

        generated_x = self.image_width + self.margin
        generated_y = 0

        # Fill generated area with average color
        painter.fillRect(generated_x, generated_y, self.generated_width, self.generated_height, self.generated_background_color)

        if self.shapes:
            self.draw_generated_image(painter, generated_x, generated_y)

    def draw_generated_image(self, painter, x_offset, y_offset):
        for shape in self.shapes:
            painter.setBrush(QBrush(QColor(*shape.color, int(shape.opacity * 255)), Qt.BrushStyle.SolidPattern))
            painter.setPen(Qt.PenStyle.NoPen)
            if shape.shape_type == "rectangle":
                painter.drawRect(shape.position[0] + x_offset, shape.position[1] + y_offset, shape.size, shape.size)
            else:
                painter.drawEllipse(QPoint(shape.position[0] + x_offset, shape.position[1] + y_offset), shape.size, shape.size)

    def get_color_at(self, x, y):
        if not hasattr(self, "original_image") or self.original_image is None:
            return QColor(255, 255, 255)

        if x < 0 or y < 0 or x >= self.image_width or y >= self.image_height:
            return QColor(255, 255, 255)

        r, g, b = self.original_image.getpixel((x, y))
        return QColor(r, g, b)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Artistic Composition Generator")
        self.setGeometry(100, 100, 1200, 600)
        self.current_image_basename = ""
        self.special_case = False
        self.girl_case = False

        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        open_action = QAction("Open Image", self)
        open_action.triggered.connect(self.open_image)
        file_menu.addAction(open_action)

        save_action = QAction("Save Image", self)
        save_action.triggered.connect(self.save_final_image)
        file_menu.addAction(save_action)

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        settings_menu = menubar.addMenu("Settings")
        self.shape_action = QAction("Use Rectangles", self, checkable=True)
        self.shape_action.toggled.connect(self.toggle_shape)
        settings_menu.addAction(self.shape_action)

        set_shapes_action = QAction("Set Number of Shapes", self)
        set_shapes_action.triggered.connect(self.set_number_of_shapes)
        settings_menu.addAction(set_shapes_action)

        set_opacity_action = QAction("Set Shape Opacity", self)
        set_opacity_action.triggered.connect(self.set_shape_opacity)
        settings_menu.addAction(set_opacity_action)

        set_max_size_action = QAction("Set Max Rectangle Size", self)
        set_max_size_action.triggered.connect(self.set_max_rectangle_size)
        settings_menu.addAction(set_max_size_action)

        self.canvas = Canvas()
        self.setCentralWidget(self.canvas)

        self.timer = QTimer()
        self.timer.timeout.connect(self.add_shape_step)
        self.steps = 0
        self.max_steps = 60000
        self.output_dir = "output_steps"
        os.makedirs(self.output_dir, exist_ok=True)
        self.progressive_save_intervals = [int(self.canvas.num_shapes * (i / 8)) for i in range(1, 9)]

    def toggle_shape(self, checked):
        self.canvas.use_rectangles = checked
        self.canvas.clear_shapes()
        self.steps = 0
        self.timer.start(1)

    def set_number_of_shapes(self):
        num, ok = QInputDialog.getInt(self, "Set Number of Shapes", "Number of shapes to generate:", self.canvas.num_shapes, 1, 1000000)
        if ok:
            self.canvas.num_shapes = num

    def set_shape_opacity(self):
        opacity, ok = QInputDialog.getDouble(self, "Set Shape Opacity", "Opacity (0.0 to 1.0):", self.canvas.opacity, 0.0, 1.0, 2)
        if ok:
            self.canvas.opacity = opacity

    def set_max_rectangle_size(self):
        max_size, ok = QInputDialog.getInt(self, "Set Max Size", "Maximum rectangle size:", self.canvas.max_rect_size, 1, 100)
        if ok:
            self.canvas.max_rect_size = max_size

    def open_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Image", "", "Images (*.png *.jpg *.jpeg)")
        if path:
            self.current_image_basename = os.path.splitext(os.path.basename(path))[0]
            # Check if the image is Girl with Pearl Earring
            if "girl" in path.lower() and "pearl" in path.lower():
                self.girl_case = True
                self.canvas.use_rectangles = True
                self.shape_action.setChecked(True)
                self.shape_action.setEnabled(False)  # Disable toggle for rectangles
            else:
                self.girl_case = False
                self.shape_action.setEnabled(True)
            self.canvas.load_image(path)
            self.steps = 0
            self.canvas.clear_shapes()
            self.timer.start(1)

    def add_shape_step(self):
        if self.steps >= self.canvas.num_shapes:
            self.timer.stop()
            if self.girl_case or self.canvas.use_rectangles:
                self.save_rectangle_final_image()
            else:
                self.save_final_image()
                self.create_movie()
            return

        w, h = self.canvas.image_width, self.canvas.image_height
        x, y = random.randint(0, w-1), random.randint(0, h-1)
        color = self.canvas.get_color_at(x, y)

        if self.canvas.use_rectangles:
            size = random.randint(1, self.canvas.max_rect_size)
            shape_type = "rectangle"
        else:
            size = random.randint(1, 6)
            shape_type = "circle"

        shape = Shape((x, y), size, (color.red(), color.green(), color.blue()), self.canvas.opacity, shape_type)
        self.canvas.add_shape(shape)

        # Save progressive images for rectangles
        if self.canvas.use_rectangles:
            intervals = [int(self.canvas.num_shapes * (i / 4)) for i in range(1, 5)]
            if self.steps in intervals:
                step_number = intervals.index(self.steps) + 1
                self.save_rectangle_progressive_image(step_number)

        self.steps += 1

    def save_rectangle_progressive_image(self, step_number):
        path = os.path.join(self.output_dir, f"rectangle_{self.current_image_basename}_step_{step_number}.png")
        pixmap = self.canvas.grab()
        pixmap.save(path)
        print(f"Saved: {path}")

    def save_rectangle_final_image(self):
        path = os.path.join(self.output_dir, f"rectangle_final_{self.current_image_basename}.png")
        pixmap = self.canvas.grab()
        pixmap.save(path)
        print(f"Final rectangle image saved at {path}")

    def save_final_image(self):
        path = os.path.join(self.output_dir, f"final_{self.current_image_basename}.png")
        pixmap = self.canvas.grab()
        pixmap.save(path)
        print(f"Saved Final Image: {path}")

    def create_movie(self):
        video_path = os.path.join(self.output_dir, "output_movie.mp4")
        command = f"ffmpeg -r 10 -i {self.output_dir}/step_%d.png -vcodec libx264 -crf 25 -pix_fmt yuv420p {video_path}"
        os.system(command)
        if os.path.exists(video_path):
            print(f"Movie created successfully: {video_path}")
        else:
            print("Error: Movie creation failed. Ensure FFmpeg is installed.")
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())