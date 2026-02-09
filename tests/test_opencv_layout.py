"""Tests for OpenCV layout analysis."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from preocr.analysis import opencv_layout


def test_analyze_with_opencv_no_libraries():
    """Test that function returns None when OpenCV/PyMuPDF not available."""
    with patch("preocr.opencv_layout.cv2", None):
        with patch("preocr.opencv_layout.fitz", None):
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                f.write(b"%PDF-1.4\n")
                temp_path = f.name

            try:
                result = opencv_layout.analyze_with_opencv(temp_path)
                assert result is None
            finally:
                Path(temp_path).unlink()


def test_analyze_with_opencv_structure():
    """Test that OpenCV analysis returns correct structure when available."""
    # Mock OpenCV and PyMuPDF
    mock_img = MagicMock()
    mock_img.shape = (100, 100)

    with patch("preocr.opencv_layout.cv2") as mock_cv2:
        with patch("preocr.opencv_layout.np") as mock_np:
            with patch("preocr.opencv_layout.fitz") as mock_fitz:
                # Mock PyMuPDF
                mock_doc = MagicMock()
                mock_page = MagicMock()
                mock_pix = MagicMock()
                mock_pix.height = 100
                mock_pix.width = 100
                mock_pix.n = 1  # Grayscale
                mock_pix.samples = b"\x00" * 10000
                mock_page.get_pixmap.return_value = mock_pix
                mock_doc.__len__.return_value = 1
                mock_doc.__getitem__.return_value = mock_page
                mock_fitz.open.return_value = mock_doc
                mock_fitz.Matrix.return_value = MagicMock()

                # Mock numpy
                mock_np.frombuffer.return_value = mock_np.array.return_value
                mock_np.array.return_value.reshape.return_value = mock_img
                mock_np.uint8 = int

                # Mock OpenCV
                mock_cv2.cvtColor.return_value = mock_img
                mock_cv2.threshold.return_value = (127, mock_img)
                mock_cv2.getStructuringElement.return_value = MagicMock()
                mock_cv2.dilate.return_value = mock_img
                mock_cv2.findContours.return_value = ([], None)
                mock_cv2.Canny.return_value = mock_img
                mock_cv2.contourArea.return_value = 100
                mock_cv2.boundingRect.return_value = (0, 0, 10, 10)

                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                    f.write(b"%PDF-1.4\n")
                    temp_path = f.name

                try:
                    result = opencv_layout.analyze_with_opencv(temp_path)

                    if result is not None:
                        assert isinstance(result, dict)
                        assert "text_regions" in result
                        assert "image_regions" in result
                        assert "text_coverage" in result
                        assert "image_coverage" in result
                        assert "layout_complexity" in result
                        assert "has_text_regions" in result
                        assert "has_image_regions" in result
                finally:
                    Path(temp_path).unlink()


def test_contours_overlap():
    """Test contour overlap detection."""
    # Skip if cv2 not available
    pytest.importorskip("cv2", reason="OpenCV not available (optional dependency)")

    # Mock contours
    contour1 = MagicMock()
    contour2 = MagicMock()

    with patch("preocr.opencv_layout.cv2") as mock_cv2:
        mock_cv2.boundingRect.side_effect = [
            (0, 0, 10, 10),  # contour1
            (5, 5, 10, 10),  # contour2 (overlaps)
        ]

        result = opencv_layout._contours_overlap(contour1, contour2)
        assert isinstance(result, bool)


def test_contours_overlap_no_cv2():
    """Test that _contours_overlap returns False when cv2 is None."""
    with patch("preocr.opencv_layout.cv2", None):
        contour1 = MagicMock()
        contour2 = MagicMock()

        result = opencv_layout._contours_overlap(contour1, contour2)
        assert result is False


def test_analyze_layout_structure():
    """Test layout analysis structure."""
    np = pytest.importorskip("numpy", reason="NumPy not available (optional dependency)")

    # Create a simple test image
    test_img = np.zeros((100, 100), dtype=np.uint8)
    test_img[10:30, 10:30] = 255  # Some white region

    with patch("preocr.opencv_layout.cv2") as mock_cv2:
        mock_cv2.ADAPTIVE_THRESH_GAUSSIAN_C = 1
        mock_cv2.THRESH_BINARY_INV = 0
        mock_cv2.MORPH_RECT = 0
        mock_cv2.RETR_EXTERNAL = 0
        mock_cv2.CHAIN_APPROX_SIMPLE = 0
        mock_cv2.adaptiveThreshold.return_value = test_img
        mock_cv2.getStructuringElement.return_value = MagicMock()
        mock_cv2.dilate.return_value = test_img
        mock_cv2.findContours.return_value = ([], None)
        mock_cv2.Canny.return_value = test_img
        mock_cv2.contourArea.return_value = 100
        mock_cv2.boundingRect.return_value = (0, 0, 10, 10)
        mock_cv2.filter2D.return_value = np.zeros((100, 100), dtype=np.float32)

        result = opencv_layout._analyze_layout(test_img, cv2_module=mock_cv2, np_module=np)

        assert isinstance(result, dict)
        assert "text_regions" in result
        assert "image_regions" in result
        assert "text_coverage" in result
        assert "image_coverage" in result
        assert "layout_complexity" in result
        assert result["layout_complexity"] in ["simple", "moderate", "complex"]
