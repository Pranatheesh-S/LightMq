"""Add or edit a bookmark and choose its destination folder."""

from PySide6.QtWidgets import QComboBox,QDialog,QDialogButtonBox,QFormLayout,QLineEdit,QMessageBox,QPushButton,QVBoxLayout,QWidget
from browser.features.bookmarks.bookmark_manager import BookmarkItem,BookmarkManager


class BookmarkDialog(QDialog):
    """Shared functional add/edit bookmark form."""

    def __init__(self,title:str,url:str,bookmark_manager:BookmarkManager|None=None,parent:QWidget|None=None,item:BookmarkItem|None=None):
        super().__init__(parent)
        self._manager=bookmark_manager or BookmarkManager.get_instance();self._item=item
        self.setWindowTitle("Edit Bookmark" if item else "Add Bookmark");self.resize(440,220)
        layout=QVBoxLayout(self);form=QFormLayout()
        self.edit_name=QLineEdit(title,self);self.edit_url=QLineEdit(url,self);self.folder=QComboBox(self)
        for folder in self._manager.folders():self.folder.addItem(folder.title,folder.id)
        target=item.parent_id if item else self._manager.BAR_ROOT_ID
        index=self.folder.findData(target)
        if index>=0:self.folder.setCurrentIndex(index)
        form.addRow("Name:",self.edit_name);form.addRow("URL:",self.edit_url);form.addRow("Folder:",self.folder);layout.addLayout(form)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel,self)
        self.btn_remove=QPushButton("Remove",self);self.btn_remove.setVisible(item is not None)
        self.btn_remove.clicked.connect(self._remove);buttons.addButton(self.btn_remove,QDialogButtonBox.ButtonRole.DestructiveRole)
        buttons.accepted.connect(self._save);buttons.rejected.connect(self.reject);layout.addWidget(buttons)

    def _save(self):
        try:
            if self._item:self._manager.update_item(self._item.id,self.edit_name.text(),self.edit_url.text(),int(self.folder.currentData()))
            else:self._manager.create_bookmark(self.edit_name.text(),self.edit_url.text(),int(self.folder.currentData()))
        except ValueError as exc:QMessageBox.warning(self,"Bookmark not saved",str(exc));return
        self.accept()

    def _remove(self):
        if self._item:self._manager.delete_item(self._item.id)
        else:self._manager.remove_bookmark(self.edit_url.text())
        self.accept()
