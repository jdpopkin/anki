# Copyright: Damien Elmes <anki@ichi2.net>
# License: GNU GPL, version 3 or later; http://www.gnu.org/copyleft/gpl.html

from PyQt4.QtGui import *
from PyQt4.QtCore import *
from PyQt4.QtWebKit import QWebPage, QWebView
import re
from anki.consts import *
#from anki.models import *
#from anki.facts import *
import aqt
from anki.sound import playFromText, clearAudioQueue
from aqt.utils import saveGeom, restoreGeom, getBase, mungeQA, \
     saveSplitter, restoreSplitter, showInfo, isMac, isWin
from anki.hooks import runFilter

class ResizingTextEdit(QTextEdit):
    def sizeHint(self):
        return QSize(200, 800)

class CardLayout(QDialog):

    # type is previewCards() type
    def __init__(self, mw, fact, type=0, ord=0, parent=None):
        QDialog.__init__(self, parent or mw, Qt.Window)
        self.mw = aqt.mw
        self.fact = fact
        self.type = type
        self.ord = ord
        self.deck = self.mw.deck
        self.model = fact.model()
        self.form = aqt.forms.clayout.Ui_Dialog()
        self.form.setupUi(self)
        self.plastiqueStyle = None
        if isMac or isWin:
            self.plastiqueStyle = QStyleFactory.create("plastique")
        # FIXME: add editing
        self.form.editTemplates.hide()
        self.connect(self.form.buttonBox, SIGNAL("helpRequested()"),
                     self.onHelp)
        self.setupCards()
        self.setupFields()
        restoreSplitter(self.form.splitter, "clayout")
        restoreGeom(self, "CardLayout")
        self.reload()
        if not self.cards:
            showInfo(_("Please enter some text first."),
                     parent=parent or mw)
            return
        self.exec_()

    def reload(self):
        self.cards = self.deck.previewCards(self.fact, self.type)
        self.fillCardList()
        self.fillFieldList()
        self.fieldChanged(0)
        self.readField()

    # Cards & Preview
    ##########################################################################

    def setupCards(self):
        self.updatingCards = False
        self.playedAudio = {}
        f = self.form
        if type == 0:
            f.templateType.setText(
                _("Templates used by fact:"))
        elif type == 1:
            f.templateType.setText(
                _("Templates that will be created:"))
        else:
            f.templateType.setText(
                _("All templates:"))
        # replace with more appropriate size hints
        for e in ("cardQuestion", "cardAnswer"):
            w = getattr(f, e)
            idx = f.templateLayout.indexOf(w)
            r = f.templateLayout.getItemPosition(idx)
            f.templateLayout.removeWidget(w)
            w.hide()
            w.deleteLater()
            w = ResizingTextEdit(self)
            setattr(f, e, w)
            f.templateLayout.addWidget(w, r[0], r[1])
        self.connect(f.cardList, SIGNAL("activated(int)"),
                     self.cardChanged)
        # self.connect(f.editTemplates, SIGNAL("clicked())"),
        #              self.onEdit)
        c = self.connect
        c(f.cardQuestion, SIGNAL("textChanged()"), self.formatChanged)
        c(f.cardAnswer, SIGNAL("textChanged()"), self.formatChanged)
        c(f.alignment, SIGNAL("activated(int)"), self.saveCard)
        c(f.background, SIGNAL("clicked()"),
                     lambda w=f.background:\
                     self.chooseColour(w, "card"))
        c(f.questionInAnswer, SIGNAL("clicked()"), self.saveCard)
        c(f.allowEmptyAnswer, SIGNAL("clicked()"), self.saveCard)
        c(f.typeAnswer, SIGNAL("activated(int)"), self.saveCard)
        c(f.flipButton, SIGNAL("clicked()"), self.onFlip)
        def linkClicked(url):
            QDesktopServices.openUrl(QUrl(url))
        f.preview.page().setLinkDelegationPolicy(
            QWebPage.DelegateExternalLinks)
        self.connect(f.preview,
                     SIGNAL("linkClicked(QUrl)"),
                     linkClicked)
        if self.plastiqueStyle:
            f.background.setStyle(self.plastiqueStyle)
        f.alignment.addItems(
                QStringList(alignmentLabels().values()))
        self.typeFieldNames = self.model.fieldMap()
        s = [_("Don't ask me to type in the answer")]
        s += [_("Compare with field '%s'") % fi
              for fi in self.typeFieldNames.keys()]
        f.typeAnswer.insertItems(0, QStringList(s))

    def formatToScreen(self, fmt):
        fmt = fmt.replace("}}<br>", "}}\n")
        return fmt

    def screenToFormat(self, fmt):
        fmt = fmt.replace("}}\n", "}}<br>")
        return fmt

    # def onEdit(self):
    #     ui.modelproperties.ModelProperties(
    #         self, self.deck, self.model, self.mw,
    #         onFinish=self.updateModelsList)

    def formatChanged(self):
        if self.updatingCards:
            return
        text = unicode(self.form.cardQuestion.toPlainText())
        self.card.template()['qfmt'] = self.screenToFormat(text)
        text = unicode(self.form.cardAnswer.toPlainText())
        self.card.template()['afmt'] = self.screenToFormat(text)
        self.renderPreview()

    def onFlip(self):
        q = unicode(self.form.cardQuestion.toPlainText())
        a = unicode(self.form.cardAnswer.toPlainText())
        self.form.cardAnswer.setPlainText(q)
        self.form.cardQuestion.setPlainText(a)

    def readCard(self):
        self.updatingCards = True
        t = self.card.template()
        f = self.form
        f.background.setPalette(QPalette(QColor(t['bg'])))
        f.cardQuestion.setPlainText(self.formatToScreen(t['qfmt']))
        f.cardAnswer.setPlainText(self.formatToScreen(t['afmt']))
        f.questionInAnswer.setChecked(t['hideQ'])
        f.allowEmptyAnswer.setChecked(t['emptyAns'])
        f.alignment.setCurrentIndex(t['align'])
        if t['typeAns'] is None:
            f.typeAnswer.setCurrentIndex(0)
        else:
            f.typeAnswer.setCurrentIndex(t['typeAns'] + 1)
        self.updatingCards = False

    def fillCardList(self):
        self.form.cardList.clear()
        cards = []
        idx = 0
        for n, c in enumerate(self.cards):
            if c.ord == self.ord:
                cards.append(_("%s (current)") % c.template()['name'])
                idx = n
            else:
                cards.append(c.template()['name'])
        self.form.cardList.addItems(
            QStringList(cards))
        self.form.editTemplates.setEnabled(False)
        self.form.cardList.setCurrentIndex(idx)
        self.cardChanged(idx)
        self.form.cardList.setFocus()

    def cardChanged(self, idx):
        self.card = self.cards[idx]
        self.readCard()
        self.renderPreview()

    def saveCard(self):
        if self.updatingCards:
            return
        card = self.card.cardModel
        card.questionAlign = self.form.alignment.currentIndex()
        card.lastFontColour = unicode(
            self.form.background.palette().window().color().name())
        card.questionInAnswer = self.form.questionInAnswer.isChecked()
        card.allowEmptyAnswer = self.form.allowEmptyAnswer.isChecked()
        idx = self.form.typeAnswer.currentIndex()
        if not idx:
            card.typeAnswer = u""
        else:
            card.typeAnswer = self.typeFieldNames[idx-1]
        card.model.setModified()
        self.deck.flushMod()
        self.renderPreview()

    def chooseColour(self, button, type="field"):
        new = QColorDialog.getColor(button.palette().window().color(), self,
                                    _("Choose Color"),
                                    QColorDialog.DontUseNativeDialog)
        if new.isValid():
            button.setPalette(QPalette(new))
            if type == "field":
                self.saveField()
            else:
                self.saveCard()

    def renderPreview(self):
        c = self.card
        styles = self.model.genCSS()
        self.form.preview.setHtml(
            ('<html><head>%s</head><body>' % getBase(self.deck, c)) +
            "<style>" + styles + "</style>" +
            mungeQA(c.q(reload=True)) +
            "<hr>" +
            mungeQA(c.a())
            + "</body></html>")
        clearAudioQueue()
        if c.id not in self.playedAudio:
            playFromText(c.q())
            playFromText(c.a())
            self.playedAudio[c.id] = True

    def reject(self):
        return
        self.fact.model.setModified()

        modified = False
        self.mw.startProgress()
        self.deck.updateProgress(_("Applying changes..."))
        reset=True
        if len(self.fieldOrdinalUpdatedIds) > 0:
            self.deck.rebuildFieldOrdinals(self.model.id, self.fieldOrdinalUpdatedIds)
            modified = True
        if self.needFieldRebuild:
            modified = True
        if modified:
            self.fact.model.setModified()
            self.deck.flushMod()
            if self.factedit and self.factedit.onChange:
                self.factedit.onChange("all")
                reset=False
        if reset:
            self.mw.reset()
        self.deck.finishProgress()
        saveGeom(self, "CardLayout")
        saveSplitter(self.form.splitter, "clayout")
        QDialog.reject(self)

    def onHelp(self):
        aqt.openHelp("CardLayout")

    # Fields
    ##########################################################################

    def setupFields(self):
        self.fieldOrdinalUpdatedIds = []
        self.updatingFields = False
        self.needFieldRebuild = False
        self.connect(self.form.fieldList, SIGNAL("currentRowChanged(int)"),
                     self.fieldChanged)
        self.connect(self.form.fieldAdd, SIGNAL("clicked()"),
                     self.addField)
        self.connect(self.form.fieldDelete, SIGNAL("clicked()"),
                     self.deleteField)
        self.connect(self.form.fieldUp, SIGNAL("clicked()"),
                     self.moveFieldUp)
        self.connect(self.form.fieldDown, SIGNAL("clicked()"),
                     self.moveFieldDown)
        self.connect(self.form.fieldName, SIGNAL("lostFocus()"),
                     self.fillFieldList)
        self.connect(self.form.fontFamily, SIGNAL("currentFontChanged(QFont)"),
                     self.saveField)
        self.connect(self.form.fontSize, SIGNAL("valueChanged(int)"),
                     self.saveField)
        self.connect(self.form.fontSizeEdit, SIGNAL("valueChanged(int)"),
                     self.saveField)
        self.connect(self.form.fieldName, SIGNAL("textEdited(QString)"),
                     self.saveField)
        self.connect(self.form.preserveWhitespace, SIGNAL("stateChanged(int)"),
                     self.saveField)
        self.connect(self.form.fieldUnique, SIGNAL("stateChanged(int)"),
                     self.saveField)
        self.connect(self.form.fieldRequired, SIGNAL("stateChanged(int)"),
                     self.saveField)
        self.connect(self.form.numeric, SIGNAL("stateChanged(int)"),
                     self.saveField)
        w = self.form.fontColour
        if self.plastiqueStyle:
            w.setStyle(self.plastiqueStyle)
        self.connect(w, SIGNAL("clicked()"),
                     lambda w=w: self.chooseColour(w))
        self.connect(self.form.rtl,
                     SIGNAL("stateChanged(int)"),
                     self.saveField)

    def fieldChanged(self, idx):
        if self.updatingFields:
            return
        self.field = self.model.fields[idx]
        self.readField()
        self.enableFieldMoveButtons()

    def readField(self):
        fld = self.field
        f = self.form
        self.updatingFields = True
        f.fieldName.setText(fld['name'])
        f.fieldUnique.setChecked(fld['uniq'])
        f.fieldRequired.setChecked(fld['req'])
        f.fontFamily.setCurrentFont(QFont(fld['font']))
        f.fontSize.setValue(fld['qsize'])
        f.fontSizeEdit.setValue(fld['esize'])
        f.fontColour.setPalette(QPalette(QColor(fld['qcol'])))
        f.rtl.setChecked(fld['rtl'])
        f.preserveWhitespace.setChecked(fld['pre'])
        self.updatingFields = False

    def saveField(self, *args):
        self.needFieldRebuild = True
        if self.updatingFields:
            return
        self.updatingFields = True
        field = self.field
        name = unicode(self.form.fieldName.text()) or _("Field")
        if field.name != name:
            oldVal = self.fact[field.name]
            self.deck.renameFieldModel(self.model, field, name)
            # the card models will have been updated
            self.readCard()
            # for add card case
            self.updateFact()
            self.fact[name] = oldVal
        field.unique = self.form.fieldUnique.isChecked()
        field.required = self.form.fieldRequired.isChecked()
        field.numeric = self.form.numeric.isChecked()
        field.quizFontFamily = toCanonicalFont(unicode(
            self.form.fontFamily.currentFont().family()))
        field.quizFontSize = int(self.form.fontSize.value())
        field.editFontSize = int(self.form.fontSizeEdit.value())
        field.quizFontColour = str(
            self.form.fontColour.palette().window().color().name())
        if self.form.rtl.isChecked():
            field.features = u"rtl"
        else:
            field.features = u""
        if self.form.preserveWhitespace.isChecked():
            field.editFontFamily = u"preserve"
        else:
            field.editFontFamily = u""
        field.model.setModified()
        self.deck.flushMod()
        self.renderPreview()
        self.fillFieldList()
        self.updatingFields = False

    def fillFieldList(self, row = None):
        oldRow = self.form.fieldList.currentRow()
        if oldRow == -1:
            oldRow = 0
        self.form.fieldList.clear()
        n = 1
        for field in self.model.fields:
            label = field['name']
            item = QListWidgetItem(label)
            self.form.fieldList.addItem(item)
            n += 1
        count = self.form.fieldList.count()
        if row != None:
            self.form.fieldList.setCurrentRow(row)
        else:
            while (count > 0 and oldRow > (count - 1)):
                    oldRow -= 1
            self.form.fieldList.setCurrentRow(oldRow)
        self.enableFieldMoveButtons()

    def enableFieldMoveButtons(self):
        row = self.form.fieldList.currentRow()
        if row < 1:
            self.form.fieldUp.setEnabled(False)
        else:
            self.form.fieldUp.setEnabled(True)
        if row == -1 or row >= (self.form.fieldList.count() - 1):
            self.form.fieldDown.setEnabled(False)
        else:
            self.form.fieldDown.setEnabled(True)

    def addField(self):
        f = FieldModel(required=False, unique=False)
        f.name = _("Field %d") % (len(self.model.fieldModels) + 1)
        self.deck.addFieldModel(self.model, f)
        try:
            self.deck.db.refresh(self.fact)
        except:
            # not yet added
            self.updateFact()
        self.fillFieldList()
        self.form.fieldList.setCurrentRow(len(self.model.fieldModels)-1)
        self.form.fieldName.setFocus()
        self.form.fieldName.selectAll()

    def updateFact(self):
        oldFact = self.fact
        model = self.deck.db.query(Model).get(oldFact.model.id)
        fact = self.deck.newFact(model)
        for field in fact.fields:
            try:
                fact[field.name] = oldFact[field.name]
            except KeyError:
                fact[field.name] = u""
        fact.tags = oldFact.tags
        self.fact = fact

    def deleteField(self):
        row = self.form.fieldList.currentRow()
        if row == -1:
            return
        if len(self.model.fieldModels) < 2:
            ui.utils.showInfo(
                _("Please add a new field first."),
                parent=self)
            return
        field = self.model.fieldModels[row]
        count = self.deck.fieldModelUseCount(field)
        if count:
            if not ui.utils.askUser(
                _("This field is used by %d cards. If you delete it,\n"
                  "all information in this field will be lost.\n"
                  "\nReally delete this field?") % count,
                parent=self):
                return
        self.deck.deleteFieldModel(self.model, field)
        self.fillFieldList()
        # need to update q/a format
        self.readCard()

    def moveFieldUp(self):
        row = self.form.fieldList.currentRow()
        if row == -1:
            return
        if row == 0:
            return
        field = self.model.fieldModels[row]
        tField = self.model.fieldModels[row - 1]
        self.model.fieldModels.remove(field)
        self.model.fieldModels.insert(row - 1, field)
        if field.id not in self.fieldOrdinalUpdatedIds:
            self.fieldOrdinalUpdatedIds.append(field.id)
        if tField.id not in self.fieldOrdinalUpdatedIds:
            self.fieldOrdinalUpdatedIds.append(tField.id)
        self.fillFieldList(row - 1)

    def moveFieldDown(self):
        row = self.form.fieldList.currentRow()
        if row == -1:
            return
        if row == len(self.model.fieldModels) - 1:
            return
        field = self.model.fieldModels[row]
        tField = self.model.fieldModels[row + 1]
        self.model.fieldModels.remove(field)
        self.model.fieldModels.insert(row + 1, field)
        if field.id not in self.fieldOrdinalUpdatedIds:
            self.fieldOrdinalUpdatedIds.append(field.id)
        if tField.id not in self.fieldOrdinalUpdatedIds:
            self.fieldOrdinalUpdatedIds.append(tField.id)
        self.fillFieldList(row + 1)
