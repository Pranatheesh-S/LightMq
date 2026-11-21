"""Tests for download path handling and display formatting."""

from browser.features.downloads.download_utils import (
    default_download_directory,
    format_duration,
    format_size,
    preserve_file_extension,
    safe_filename,
)


def test_safe_filename_rejects_path_components_and_reserved_characters():
    assert safe_filename("../../folder\\report.pdf") == "report.pdf"
    assert safe_filename("C:\\temp\\bad:name?.txt") == "bad_name_.txt"
    assert safe_filename("../..") == "download"
    assert safe_filename("CON.txt") == "_CON.txt"
    assert ".." not in safe_filename("..\\..\\secret.exe")


def test_download_formatting_handles_unknown_and_boundary_values():
    assert format_size(0) == "0 B"
    assert format_size(1024) == "1.0 KB"
    assert format_size(-1) == "Unknown size"
    assert format_duration(0) == "0 sec remaining"
    assert format_duration(3661) == "1 hr 1 min remaining"
    assert format_duration(float("inf")) == ""


def test_default_download_directory_is_a_path():
    assert default_download_directory().is_absolute()


def test_download_preserves_original_file_extension():
    mime_cases = {
        "application/pdf": "resume.pdf",
        "image/png": "resume.png",
        "image/jpeg": "resume.jpg",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "resume.docx",
        "video/mp4": "resume.mp4",
        "application/vnd.api+json": "resume.json",
        "font/woff2": "resume.woff2",
        "application/x-7z-compressed": "resume.7z",
    }
    for mime_type, expected in mime_cases.items():
        assert preserve_file_extension("resume", "resume", mime_type) == expected

    assert preserve_file_extension(
        "renamed", "resume.pdf", "application/octet-stream"
    ) == "renamed.pdf"
    assert preserve_file_extension(
        "archive", "archive", "application/octet-stream", "https://example.test/a.zip"
    ) == "archive.zip"
    assert preserve_file_extension("notes.txt", "resume.pdf", "application/pdf") == "notes.txt"
