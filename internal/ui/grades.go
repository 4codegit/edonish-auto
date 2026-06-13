// GradesTab — вкладка журнала оценок.
// Отображает таблицу учеников с оценками, позволяет редактировать оценки,
// заполнять случайными значениями и просматривать статистику ученика.
// Это самая важная вкладка приложения.
package ui

import (
	"fmt"
	"math"
	"math/rand"
	"strings"

	"fyne.io/fyne/v2"
	"fyne.io/fyne/v2/canvas"
	"fyne.io/fyne/v2/container"
	"fyne.io/fyne/v2/dialog"
	"fyne.io/fyne/v2/layout"
	"fyne.io/fyne/v2/theme"
	"fyne.io/fyne/v2/widget"

	"github.com/4codegit/edonish-auto/internal/config"
	"github.com/4codegit/edonish-auto/internal/edonish"
)

// studentGradeLimits — лимиты оценок для каждого ученика
type studentGradeLimits struct {
	MinGrade int // Минимальная оценка
	MaxGrade int // Максимальная оценка
}

// GradesTab — вкладка журнала оценок
type GradesTab struct {
	app         *App                           // Ссылка на приложение
	container_  *fyne.Container                // Корневой контейнер
	client      *edonish.EdonishClient         // Клиент API
	journalOpts *edonish.JournalOptions        // Опции журнала (классы, предметы)
	dates       []edonish.JournalDate          // Даты текущей четверти
	students    []edonish.JournalStudent       // Ученики с оценками
	limits      map[string]*studentGradeLimits // Лимиты оценок по ученикам

	// Элементы фильтра
	classSel   *widget.Select // Выбор класса
	subjectSel *widget.Select // Выбор предмета
	quarterSel *widget.Select // Выбор четверти

	// Данные выбранных фильтров
	selectedGroupID   int // ID выбранного класса
	selectedSubjectID int // ID выбранного предмета
	selectedQuarterID int // ID выбранной четверти

	// Таблица и состояние
	table              *widget.Table   // Таблица оценок
	statusLabel        *widget.Label   // Статус загрузки
	detailBox          *fyne.Container // Панель деталей ученика
	selectedStudentIdx int             // Индекс выбранного ученика (-1 = не выбран)
}

// NewGradesTab создаёт вкладку оценок
func NewGradesTab(app *App) *GradesTab {
	g := &GradesTab{
		app:                app,
		client:             app.GetClient(),
		limits:             make(map[string]*studentGradeLimits),
		selectedStudentIdx: -1,
	}

	// Загружаем опции журнала
	go g.loadJournalOptions()

	return g
}

// Container возвращает корневой контейнер вкладки
func (g *GradesTab) Container() fyne.CanvasObject {
	if g.container_ == nil {
		g.buildUI()
	}
	return g.container_
}

// buildUI создаёт интерфейс вкладки оценок
func (g *GradesTab) buildUI() {
	// Фильтры
	g.classSel = widget.NewSelect([]string{}, g.onClassSelected)
	g.classSel.PlaceHolder = "Выберите класс..."

	g.subjectSel = widget.NewSelect([]string{}, g.onSubjectSelected)
	g.subjectSel.PlaceHolder = "Выберите предмет..."

	g.quarterSel = widget.NewSelect([]string{}, g.onQuarterSelected)
	g.quarterSel.PlaceHolder = "Выберите четверть..."

	// Статус загрузки
	g.statusLabel = widget.NewLabel("Загрузка данных журнала...")
	g.statusLabel.Wrapping = fyne.TextWrap(fyne.TextTruncate)

	// Кнопки действий
	refreshBtn := widget.NewButtonWithIcon("Обновить", theme.ViewRefreshIcon(), func() {
		go g.loadJournalOptions()
	})

	randomFillBtn := widget.NewButton("🎲 Заполнить случайно", func() {
		g.showRandomFillDialog()
	})
	randomFillBtn.Importance = widget.HighImportance

	limitsBtn := widget.NewButton("Пределы учеников", func() {
		g.showLimitsDialog()
	})

	// Панель фильтров
	filterBar := container.NewHBox(
		widget.NewLabel("Класс:"), g.classSel,
		widget.NewLabel("Предмет:"), g.subjectSel,
		widget.NewLabel("Четверть:"), g.quarterSel,
		layout.NewSpacer(),
		refreshBtn,
		limitsBtn,
		randomFillBtn,
	)

	// Таблица оценок (пустая, заполнится после загрузки)
	g.table = g.createTable()

	// Панель деталей ученика (справа)
	g.detailBox = container.NewVBox(
		widget.NewLabel("Выберите ученика"),
	)

	detailScroll := container.NewVScroll(g.detailBox)
	detailScroll.SetMinSize(fyne.NewSize(220, 0))

	// Основной контент: таблица + панель деталей
	content := container.NewBorder(
		nil, nil, nil,
		detailScroll,
		g.table,
	)

	// Корневой контейнер
	g.container_ = container.NewBorder(
		container.NewVBox(filterBar, widget.NewSeparator(), g.statusLabel),
		nil, nil, nil,
		content,
	)
}

// createTable создаёт таблицу оценок
func (g *GradesTab) createTable() *widget.Table {
	// Количество колонок: #, ФИО, даты..., Ср, Диап
	colCount := 4 // Минимум: #, ФИО, Ср, Диап
	if len(g.dates) > 0 {
		colCount = 2 + len(g.dates) + 2
	}

	rowCount := len(g.students) + 1 // +1 для заголовка

	t := widget.NewTable(
		func() (int, int) {
			return rowCount, colCount
		},
		func() fyne.CanvasObject {
			// Шаблон ячейки — используем canvas.Text для цветного текста
			t := canvas.NewText("", theme.ForegroundColor())
			t.TextSize = 13
			return t
		},
		func(id widget.TableCellID, cell fyne.CanvasObject) {
			text := cell.(*canvas.Text)
			text.Color = theme.ForegroundColor()
			text.TextStyle = fyne.TextStyle{}

			if id.Row == 0 {
				// Заголовок таблицы
				text.TextStyle = fyne.TextStyle{Bold: true}
				switch id.Col {
				case 0:
					text.Text = "№"
				case 1:
					text.Text = "Ученик"
				default:
					dateIdx := id.Col - 2
					if dateIdx < len(g.dates) {
						// Показываем только дату без времени
						dateStr := g.dates[dateIdx].AssignmentDate
						if len(dateStr) >= 10 {
							text.Text = dateStr[5:10] // MM-DD
						} else {
							text.Text = dateStr
						}
					} else if id.Col == 2+len(g.dates) {
						text.Text = "Ср"
					} else if id.Col == 2+len(g.dates)+1 {
						text.Text = "Диап"
					} else {
						text.Text = ""
					}
				}
				return
			}

			// Данные ученика
			studentIdx := id.Row - 1
			if studentIdx >= len(g.students) {
				text.Text = ""
				return
			}
			student := g.students[studentIdx]

			switch id.Col {
			case 0:
				// Номер ученика
				text.Text = fmt.Sprintf("%d", studentIdx+1)
			case 1:
				// ФИО ученика
				text.Text = student.LastName + " " + student.FirstName
			default:
				dateIdx := id.Col - 2
				if dateIdx < len(g.dates) {
					// Оценка за дату
					dateID := g.dates[dateIdx].AssignmentDateID
					mark := g.findMark(student, dateID)
					if mark != nil && mark.Mark > 0 {
						text.Text = fmt.Sprintf("%d", mark.Mark)
						text.Color = gradeColor(mark.Mark)
					} else {
						text.Text = "—"
						text.Color = theme.DisabledColor()
					}
				} else if id.Col == 2+len(g.dates) {
					// Средняя оценка
					avg := g.calcAverage(student)
					if avg > 0 {
						text.Text = fmt.Sprintf("%.1f", avg)
						text.Color = gradeColor(int(math.Round(avg)))
					} else {
						text.Text = "—"
						text.Color = theme.DisabledColor()
					}
				} else if id.Col == 2+len(g.dates)+1 {
					// Диапазон оценок
					min, max := g.calcRange(student)
					if min > 0 {
						text.Text = fmt.Sprintf("%d-%d", min, max)
					} else {
						text.Text = "—"
						text.Color = theme.DisabledColor()
					}
				} else {
					text.Text = ""
				}
			}
		},
	)

	// Обработка двойного клика для редактирования оценки
	t.OnSelected = func(id widget.TableCellID) {
		g.onCellSelected(id)
	}

	// Ширина колонок
	t.CreateHeader = nil // Используем стандартные заголовки
	t.ShowHeaderRow = true

	return t
}

// findMark находит оценку ученика за указанную дату
func (g *GradesTab) findMark(student edonish.JournalStudent, dateID string) *edonish.SubjectMark {
	for i := range student.SubjectMarks {
		if student.SubjectMarks[i].AssignmentDateID == dateID {
			return &student.SubjectMarks[i]
		}
	}
	return nil
}

// calcAverage вычисляет среднюю оценку ученика
func (g *GradesTab) calcAverage(student edonish.JournalStudent) float64 {
	var sum, count float64
	for _, m := range student.SubjectMarks {
		if m.Mark > 0 {
			sum += float64(m.Mark)
			count++
		}
	}
	if count == 0 {
		return 0
	}
	return sum / count
}

// calcRange вычисляет минимальную и максимальную оценку ученика
func (g *GradesTab) calcRange(student edonish.JournalStudent) (int, int) {
	min, max := 11, 0
	for _, m := range student.SubjectMarks {
		if m.Mark > 0 {
			if m.Mark < min {
				min = m.Mark
			}
			if m.Mark > max {
				max = m.Mark
			}
		}
	}
	if max == 0 {
		return 0, 0
	}
	return min, max
}

// gradeColor возвращает цвет для оценки по шкале edonish
func gradeColor(mark int) fyne.Color {
	switch {
	case mark == 10:
		return fyne.NewColor(0, 0.65, 0.1, 1) // Ярко-зелёный
	case mark == 9:
		return fyne.NewColor(0.1, 0.5, 0.1, 1) // Тёмно-зелёный
	case mark == 8:
		return theme.ForegroundColor() // По умолчанию
	case mark == 7:
		return fyne.NewColor(0.5, 0.5, 0.5, 1) // Серый
	case mark >= 5:
		return fyne.NewColor(0.85, 0.5, 0, 1) // Оранжевый
	case mark >= 1:
		return fyne.NewColor(0.86, 0.15, 0.15, 1) // Красный
	default:
		return fyne.NewColor(0.5, 0, 0, 1) // Тёмно-красный
	}
}

// onCellSelected обрабатывает выбор ячейки таблицы
func (g *GradesTab) onCellSelected(id widget.TableCellID) {
	if id.Row == 0 {
		return // Заголовок
	}

	studentIdx := id.Row - 1
	if studentIdx >= len(g.students) {
		return
	}

	// Если кликнули на имя ученика — показываем детали
	if id.Col == 1 {
		g.showStudentDetails(studentIdx)
		return
	}

	// Если кликнули на ячейку с оценкой — редактируем
	dateIdx := id.Col - 2
	if dateIdx >= 0 && dateIdx < len(g.dates) {
		g.showEditGradeDialog(studentIdx, dateIdx)
	}
}

// showStudentDetails показывает панель с деталями ученика
func (g *GradesTab) showStudentDetails(idx int) {
	g.selectedStudentIdx = idx
	if idx < 0 || idx >= len(g.students) {
		return
	}

	student := g.students[idx]
	avg := g.calcAverage(student)
	min, max := g.calcRange(student)

	// Очищаем панель деталей
	g.detailBox.Objects = nil

	// Имя ученика
	nameText := canvas.NewText(student.LastName+" "+student.FirstName, nil)
	nameText.TextStyle = fyne.TextStyle{Bold: true}
	nameText.TextSize = 16
	g.detailBox.Add(nameText)

	// Статистика
	g.detailBox.Add(widget.NewSeparator())
	g.detailBox.Add(widget.NewLabel(fmt.Sprintf("Средняя: %.1f", avg)))
	g.detailBox.Add(widget.NewLabel(fmt.Sprintf("Диапазон: %d — %d", min, max)))

	// Подсчёт оценок по значениям
	counts := make(map[int]int)
	total := 0
	for _, m := range student.SubjectMarks {
		if m.Mark > 0 {
			counts[m.Mark]++
			total++
		}
	}
	g.detailBox.Add(widget.NewLabel(fmt.Sprintf("Всего оценок: %d", total)))

	// Гистограмма оценок
	g.detailBox.Add(widget.NewSeparator())
	g.detailBox.Add(widget.NewLabel("Распределение:"))
	for mark := 10; mark >= 1; mark-- {
		if cnt, ok := counts[mark]; ok && cnt > 0 {
			bar := strings.Repeat("█", cnt)
			markText := canvas.NewText(fmt.Sprintf("%2d: %s (%d)", mark, bar, cnt), gradeColor(mark))
			markText.TextSize = 12
			g.detailBox.Add(markText)
		}
	}

	g.detailBox.Refresh()
}

// showEditGradeDialog показывает диалог редактирования оценки
func (g *GradesTab) showEditGradeDialog(studentIdx, dateIdx int) {
	if studentIdx >= len(g.students) || dateIdx >= len(g.dates) {
		return
	}

	student := g.students[studentIdx]
	date := g.dates[dateIdx]
	currentMark := g.findMark(student, date.AssignmentDateID)

	dialogTitle := fmt.Sprintf("Оценка: %s — %s",
		student.LastName+" "+student.FirstName,
		date.AssignmentDate[:10])

	// Текущая оценка
	currentVal := 0
	if currentMark != nil {
		currentVal = currentMark.Mark
	}

	currentLabel := widget.NewLabel(fmt.Sprintf("Текущая оценка: %d", currentVal))

	// Объявляем dlg заранее для использования в замыканиях
	var dlg dialog.Dialog

	// Кнопки быстрой установки 1-10
	buttons := container.NewGridWithColumns(5)
	for mark := 1; mark <= 10; mark++ {
		m := mark // Захватываем переменную
		btn := widget.NewButton(fmt.Sprintf("%d", m), func() {
			go g.setGrade(studentIdx, dateIdx, m)
			dlg.Hide()
		})
		buttons.Add(btn)
	}

	// Кнопка удаления оценки
	deleteBtn := widget.NewButton("Удалить оценку", func() {
		if currentMark != nil && currentMark.ID > 0 {
			go g.deleteGrade(studentIdx, dateIdx, currentMark.ID)
		}
		dlg.Hide()
	})
	deleteBtn.Importance = widget.DangerImportance

	// Создаём диалог с полным содержимым
	content := container.NewVBox(
		currentLabel,
		widget.NewSeparator(),
		widget.NewLabel("Установить оценку:"),
		buttons,
		deleteBtn,
	)

	dlg = dialog.NewCustom(dialogTitle, "Закрыть", content, g.app.GetWindow())
	dlg.Show()
}

// setGrade устанавливает оценку ученику за указанную дату
func (g *GradesTab) setGrade(studentIdx, dateIdx, mark int) {
	if studentIdx >= len(g.students) || dateIdx >= len(g.dates) {
		return
	}

	student := g.students[studentIdx]
	date := g.dates[dateIdx]

	err := g.client.CreateMark(
		student.StudentID,
		date.AssignmentDateID,
		g.selectedQuarterID,
		mark,
	)

	fyne.Do(func() {
		if err != nil {
			dialog.ShowError(err, g.app.GetWindow())
			return
		}
		g.statusLabel.SetText(fmt.Sprintf("Оценка %d установлена: %s", mark, student.LastName))
		// Обновляем данные
		go g.loadJournalData()
	})
}

// deleteGrade удаляет оценку
func (g *GradesTab) deleteGrade(studentIdx, dateIdx, markID int) {
	err := g.client.DeleteMark(markID)

	fyne.Do(func() {
		if err != nil {
			dialog.ShowError(err, g.app.GetWindow())
			return
		}
		g.statusLabel.SetText("Оценка удалена")
		go g.loadJournalData()
	})
}

// showRandomFillDialog показывает диалог случайного заполнения
func (g *GradesTab) showRandomFillDialog() {
	if len(g.students) == 0 {
		dialog.ShowInformation("Внимание", "Сначала загрузите данные журнала", g.app.GetWindow())
		return
	}

	// Выбор ученика
	studentNames := make([]string, len(g.students)+1)
	studentNames[0] = "Все ученики"
	for i, s := range g.students {
		studentNames[i+1] = s.LastName + " " + s.FirstName
	}

	studentSel := widget.NewSelect(studentNames, nil)
	studentSel.SetSelectedIndex(0)

	// Мин/Макс оценки
	minEntry := widget.NewEntry()
	minEntry.SetPlaceHolder(fmt.Sprintf("%d", config.MinGrade))
	minEntry.SetText(fmt.Sprintf("%d", config.MinGrade))

	maxEntry := widget.NewEntry()
	maxEntry.SetPlaceHolder(fmt.Sprintf("%d", config.MaxGrade))
	maxEntry.SetText(fmt.Sprintf("%d", config.MaxGrade))

	// Форма
	form := container.NewVBox(
		widget.NewLabel("Ученик:"),
		studentSel,
		widget.NewLabel("Минимальная оценка:"),
		minEntry,
		widget.NewLabel("Максимальная оценка:"),
		maxEntry,
		widget.NewSeparator(),
	)

	// Объявляем dlg заранее для использования в замыканиях
	var dlg dialog.Dialog

	// Кнопка заполнения выбранного
	fillOneBtn := widget.NewButton("Заполнить выбранного", func() {
		minVal, maxVal := parseMinMax(minEntry.Text, maxEntry.Text)
		idx := studentSel.SelectedIndex()
		if idx <= 0 {
			dialog.ShowError(&simpleError{"Выберите ученика"}, g.app.GetWindow())
			return
		}
		go g.randomFillStudent(idx-1, minVal, maxVal)
		dlg.Hide()
	})

	// Кнопка заполнения всех
	fillAllBtn := widget.NewButton("Заполнить всех", func() {
		minVal, maxVal := parseMinMax(minEntry.Text, maxEntry.Text)
		go g.randomFillAll(minVal, maxVal)
		dlg.Hide()
	})
	fillAllBtn.Importance = widget.HighImportance

	content := container.NewVBox(
		form,
		fillOneBtn,
		fillAllBtn,
	)

	dlg = dialog.NewCustom("Случайное заполнение", "Отмена", content, g.app.GetWindow())
	dlg.Show()
}

// showLimitsDialog показывает диалог лимитов оценок для каждого ученика
func (g *GradesTab) showLimitsDialog() {
	if len(g.students) == 0 {
		dialog.ShowInformation("Внимание", "Сначала загрузите данные журнала", g.app.GetWindow())
		return
	}

	// Список мин/макс для каждого ученика
	entries := container.NewVBox()
	minEntries := make([]*widget.Entry, len(g.students))
	maxEntries := make([]*widget.Entry, len(g.students))

	for i, s := range g.students {
		key := fmt.Sprintf("%d", s.StudentID)
		minVal := config.MinGrade
		maxVal := config.MaxGrade
		if lim, ok := g.limits[key]; ok {
			minVal = lim.MinGrade
			maxVal = lim.MaxGrade
		}

		minE := widget.NewEntry()
		minE.SetText(fmt.Sprintf("%d", minVal))
		minE.Wrapping = fyne.TextWrap(fyne.TextTruncate)

		maxE := widget.NewEntry()
		maxE.SetText(fmt.Sprintf("%d", maxVal))
		maxE.Wrapping = fyne.TextWrap(fyne.TextTruncate)

		minEntries[i] = minE
		maxEntries[i] = maxE

		row := container.NewGridWithColumns(3,
			widget.NewLabel(s.LastName+" "+s.FirstName),
			minE,
			maxE,
		)
		entries.Add(row)
	}

	// Заголовок
	header := container.NewGridWithColumns(3,
		widget.NewLabelWithStyle("Ученик", fyne.TextAlignLeading, fyne.TextStyle{Bold: true}),
		widget.NewLabelWithStyle("Мин", fyne.TextAlignCenter, fyne.TextStyle{Bold: true}),
		widget.NewLabelWithStyle("Макс", fyne.TextAlignCenter, fyne.TextStyle{Bold: true}),
	)

	scroll := container.NewVScroll(container.NewVBox(header, entries))
	scroll.SetMinSize(fyne.NewSize(400, 300))

	// Кнопка «Установить всем»
	setAllMin := widget.NewEntry()
	setAllMin.SetPlaceHolder(fmt.Sprintf("%d", config.MinGrade))
	setAllMax := widget.NewEntry()
	setAllMax.SetPlaceHolder(fmt.Sprintf("%d", config.MaxGrade))

	setAllBtn := widget.NewButton("Установить всем", func() {
		minVal, maxVal := parseMinMax(setAllMin.Text, setAllMax.Text)
		for i := range g.students {
			minEntries[i].SetText(fmt.Sprintf("%d", minVal))
			maxEntries[i].SetText(fmt.Sprintf("%d", maxVal))
		}
	})

	batchRow := container.NewGridWithColumns(4,
		widget.NewLabel("Всем мин:"),
		setAllMin,
		widget.NewLabel("макс:"),
		setAllMax,
	)

	// Объявляем dlg заранее для использования в замыканиях
	var dlg dialog.Dialog

	saveBtn := widget.NewButton("Сохранить", func() {
		for i, s := range g.students {
			key := fmt.Sprintf("%d", s.StudentID)
			minVal, maxVal := parseMinMax(minEntries[i].Text, maxEntries[i].Text)
			g.limits[key] = &studentGradeLimits{
				MinGrade: minVal,
				MaxGrade: maxVal,
			}
		}
		dlg.Hide()
	})

	content := container.NewBorder(
		container.NewVBox(batchRow, setAllBtn, widget.NewSeparator()),
		saveBtn,
		nil, nil,
		scroll,
	)

	dlg = dialog.NewCustom("Пределы оценок", "Отмена", content, g.app.GetWindow())
	dlg.Show()
}

// loadJournalOptions загружает опции журнала (классы, предметы, четверти)
func (g *GradesTab) loadJournalOptions() {
	opts, err := g.client.GetJournalOptions()

	fyne.Do(func() {
		if err != nil {
			g.statusLabel.SetText("Ошибка загрузки: " + err.Error())
			return
		}

		g.journalOpts = opts

		// Заполняем выпадающий список классов
		classNames := make([]string, len(opts.Groups))
		for i, group := range opts.Groups {
			classNames[i] = group.Name
		}

		if g.classSel != nil {
			g.classSel.Options = classNames
			g.classSel.Refresh()

			// Автоматически выбираем первый класс
			if len(classNames) > 0 {
				g.classSel.SetSelectedIndex(0)
			}
		}

		g.statusLabel.SetText(fmt.Sprintf("Загружено классов: %d", len(opts.Groups)))
	})
}

// onClassSelected обрабатывает выбор класса
// Обновляет списки предметов и четвертей
func (g *GradesTab) onClassSelected(selected string) {
	if g.journalOpts == nil {
		return
	}

	// Находим выбранную группу
	for _, group := range g.journalOpts.Groups {
		if group.Name == selected {
			g.selectedGroupID = group.ID

			// Обновляем предметы
			subjectNames := make([]string, len(group.Subjects))
			for i, subj := range group.Subjects {
				subjectNames[i] = subj.SubjectName
			}
			g.subjectSel.Options = subjectNames
			g.subjectSel.Refresh()
			g.subjectSel.ClearSelected()

			// Обновляем четверти
			quarterNames := make([]string, len(group.Quarters))
			for i, q := range group.Quarters {
				quarterNames[i] = q.Name
			}
			g.quarterSel.Options = quarterNames
			g.quarterSel.Refresh()

			// Автоматически выбираем текущую четверть
			for i, q := range group.Quarters {
				if q.CurrentQuarter {
					g.quarterSel.SetSelectedIndex(i)
					break
				}
			}

			// Автоматически выбираем первый предмет
			if len(subjectNames) > 0 {
				g.subjectSel.SetSelectedIndex(0)
			}

			break
		}
	}
}

// onSubjectSelected обрабатывает выбор предмета
// Загружает данные журнала для выбранного класса/предмета/четверти
func (g *GradesTab) onSubjectSelected(selected string) {
	if g.journalOpts == nil || g.selectedGroupID == 0 {
		return
	}

	// Находим ID выбранного предмета
	for _, group := range g.journalOpts.Groups {
		if group.ID == g.selectedGroupID {
			for _, subj := range group.Subjects {
				if subj.SubjectName == selected {
					g.selectedSubjectID = subj.SubjectID
					go g.loadJournalData()
					return
				}
			}
		}
	}
}

// onQuarterSelected обрабатывает выбор четверти
func (g *GradesTab) onQuarterSelected(selected string) {
	if g.journalOpts == nil || g.selectedGroupID == 0 {
		return
	}

	// Находим ID выбранной четверти
	for _, group := range g.journalOpts.Groups {
		if group.ID == g.selectedGroupID {
			for _, q := range group.Quarters {
				if q.Name == selected {
					g.selectedQuarterID = q.ID
					if g.selectedSubjectID > 0 {
						go g.loadJournalData()
					}
					return
				}
			}
		}
	}
}

// loadJournalData загружает данные журнала (даты и учеников)
func (g *GradesTab) loadJournalData() {
	if g.selectedGroupID == 0 || g.selectedSubjectID == 0 || g.selectedQuarterID == 0 {
		return
	}

	fyne.Do(func() {
		g.statusLabel.SetText("Загрузка данных журнала...")
	})

	// Загружаем даты и учеников параллельно
	type loadResult struct {
		dates    []edonish.JournalDate
		students []edonish.JournalStudent
		dateErr  error
		studErr  error
	}

	result := &loadResult{}

	// Загружаем даты
	result.dates, result.dateErr = g.client.GetJournalDates(
		g.selectedGroupID, g.selectedSubjectID, g.selectedQuarterID,
	)

	// Загружаем учеников
	result.students, result.studErr = g.client.GetJournalStudents(
		g.selectedGroupID, g.selectedSubjectID, g.selectedQuarterID,
	)

	fyne.Do(func() {
		if result.dateErr != nil {
			g.statusLabel.SetText("Ошибка загрузки дат: " + result.dateErr.Error())
			return
		}
		if result.studErr != nil {
			g.statusLabel.SetText("Ошибка загрузки учеников: " + result.studErr.Error())
			return
		}

		g.dates = result.dates
		g.students = result.students

		// Пересоздаём таблицу
		g.rebuildTable()

		g.statusLabel.SetText(fmt.Sprintf(
			"Загружено: %d учеников, %d дат",
			len(g.students), len(g.dates),
		))
	})
}

// rebuildTable пересоздаёт таблицу с текущими данными
func (g *GradesTab) rebuildTable() {
	if g.container_ == nil {
		return
	}

	// Находим контейнер таблицы и заменяем
	newTable := g.createTable()

	// Заменяем таблицу в контейнере
	// Ищем Border-контейнер и обновляем центр
	for i, obj := range g.container_.Objects {
		if border, ok := obj.(*fyne.Container); ok {
			// Это BorderLayout — обновляем центр
			g.table = newTable
			// Пересоздаём весь UI — самый простой подход
			_ = border
			break
		}
	}
	_ = newTable
	// Полная пересборка UI — надёжный подход
	g.container_ = nil
	g.buildUI()
	g.container_.Refresh()
}

// randomFillStudent заполняет пустые оценки для одного ученика случайными значениями
func (g *GradesTab) randomFillStudent(studentIdx, minVal, maxVal int) {
	if studentIdx < 0 || studentIdx >= len(g.students) {
		return
	}

	student := g.students[studentIdx]
	created := 0
	errors := 0

	for _, date := range g.dates {
		// Проверяем, есть ли уже оценка
		existingMark := g.findMark(student, date.AssignmentDateID)
		if existingMark != nil && existingMark.Mark > 0 {
			continue // Оценка уже стоит
		}

		// Генерируем случайную оценку в пределах
		mark := minVal + rand.Intn(maxVal-minVal+1)

		err := g.client.CreateMark(
			student.StudentID,
			date.AssignmentDateID,
			g.selectedQuarterID,
			mark,
		)

		if err != nil {
			errors++
		} else {
			created++
		}
	}

	fyne.Do(func() {
		g.statusLabel.SetText(fmt.Sprintf(
			"Заполнено: %d оценок, ошибок: %d (%s)",
			created, errors, student.LastName,
		))
		go g.loadJournalData()
	})
}

// randomFillAll заполняет пустые оценки для всех учеников
func (g *GradesTab) randomFillAll(minVal, maxVal int) {
	created := 0
	errors := 0

	for _, student := range g.students {
		// Проверяем лимиты для ученика
		key := fmt.Sprintf("%d", student.StudentID)
		sMin, sMax := minVal, maxVal
		if lim, ok := g.limits[key]; ok {
			sMin, sMax = lim.MinGrade, lim.MaxGrade
		}

		for _, date := range g.dates {
			// Проверяем, есть ли уже оценка
			existingMark := g.findMark(student, date.AssignmentDateID)
			if existingMark != nil && existingMark.Mark > 0 {
				continue
			}

			// Генерируем случайную оценку
			mark := sMin + rand.Intn(sMax-sMin+1)

			err := g.client.CreateMark(
				student.StudentID,
				date.AssignmentDateID,
				g.selectedQuarterID,
				mark,
			)

			if err != nil {
				errors++
			} else {
				created++
			}
		}
	}

	fyne.Do(func() {
		g.statusLabel.SetText(fmt.Sprintf(
			"Заполнено: %d оценок, ошибок: %d",
			created, errors,
		))
		go g.loadJournalData()
	})
}

// parseMinMax парсит мин/макс из строковых значений
func parseMinMax(minStr, maxStr string) (int, int) {
	minVal := config.MinGrade
	maxVal := config.MaxGrade

	if v, err := fmt.Sscanf(minStr, "%d", &minVal); v != 1 || err != nil {
		minVal = config.MinGrade
	}
	if v, err := fmt.Sscanf(maxStr, "%d", &maxVal); v != 1 || err != nil {
		maxVal = config.MaxGrade
	}

	// Ограничиваем диапазон
	if minVal < 1 {
		minVal = 1
	}
	if maxVal > 10 {
		maxVal = 10
	}
	if minVal > maxVal {
		minVal, maxVal = maxVal, minVal
	}

	return minVal, maxVal
}
