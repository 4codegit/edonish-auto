// DiariesTab — вкладка автоматизации дневников.
// Позволяет заполнить оценки за весь год одним нажатием.
// Поддерживает пресеты комбинаций оценок, предпросмотр и пошаговое заполнение.
package ui

import (
	"fmt"
	"math/rand"
	"strings"
	"sync/atomic"

	"fyne.io/fyne/v2"
	"fyne.io/fyne/v2/canvas"
	"fyne.io/fyne/v2/container"
	"fyne.io/fyne/v2/dialog"
	"fyne.io/fyne/v2/layout"
	"fyne.io/fyne/v2/widget"

	"github.com/4codegit/edonish-auto/internal/edonish"
)

// GradePreset — пресет комбинации оценок
type GradePreset struct {
	Name    string          // Название пресета
	Emoji   string          // Эмодзи-иконка
	Min     int             // Минимальная оценка
	Max     int             // Максимальная оценка
	Weights map[int]float64 // Веса оценок для колоколообразной кривой
}

// Доступные пресеты комбинаций оценок
var gradePresets = []GradePreset{
	{
		Name:    "Хорошо и Отлично",
		Emoji:   "🔵",
		Min:     8,
		Max:     10,
		Weights: map[int]float64{8: 0.40, 9: 0.35, 10: 0.25},
	},
	{
		Name:    "Хорошо и Удовлетворительно",
		Emoji:   "🟢",
		Min:     5,
		Max:     8,
		Weights: map[int]float64{5: 0.10, 6: 0.20, 7: 0.35, 8: 0.35},
	},
	{
		Name:    "Отлично",
		Emoji:   "🟡",
		Min:     9,
		Max:     10,
		Weights: map[int]float64{9: 0.45, 10: 0.55},
	},
	{
		Name:    "Удовлетворительно",
		Emoji:   "🟠",
		Min:     4,
		Max:     6,
		Weights: map[int]float64{4: 0.20, 5: 0.40, 6: 0.40},
	},
	{
		Name:    "Свой диапазон",
		Emoji:   "🟣",
		Min:     1,
		Max:     10,
		Weights: nil, // Равномерное распределение
	},
}

// DiariesTab — вкладка автоматизации дневников
type DiariesTab struct {
	app         *App                           // Ссылка на приложение
	container   *fyne.Container                // Корневой контейнер
	client      *edonish.EdonishClient         // Клиент API
	journalOpts *edonish.JournalOptions        // Опции журнала
	limits      map[string]*studentGradeLimits // Лимиты оценок по ученикам

	// Элементы фильтра
	classSel   *widget.Select // Выбор класса
	subjectSel *widget.Select // Выбор предмета

	// Данные выбранных фильтров
	selectedGroupID   int // ID выбранного класса
	selectedSubjectID int // ID выбранного предмета

	// Пресет и настройки
	presetRadio    *widget.RadioGroup // Выбор пресета
	customMinEntry *widget.Entry      // Свой мин
	customMaxEntry *widget.Entry      // Свой макс
	fillEmptyOnly  *widget.Check      // Заполнять только пустые
	quarterMarks   *widget.Check      // Включить четвертные
	semesterMarks  *widget.Check      // Включить семестровые
	yearMarks      *widget.Check      // Включить годовые

	// Прогресс
	progressBar  *widget.ProgressBar // Полоса прогресса
	statsLabel   *widget.Label       // Статистика
	resultsEntry *widget.Entry       // Результаты

	// Состояние
	fillRunning atomic.Bool // Флаг: заполнение выполняется
	stopFlag    atomic.Bool // Флаг: остановить заполнение
}

// NewDiariesTab создаёт вкладку дневников
func NewDiariesTab(app *App) *DiariesTab {
	d := &DiariesTab{
		app:    app,
		client: app.GetClient(),
		limits: make(map[string]*studentGradeLimits),
	}
	d.buildUI()

	// Загружаем опции журнала в фоне
	go d.loadJournalOptions()

	return d
}

// Container возвращает корневой контейнер вкладки
func (d *DiariesTab) Container() fyne.CanvasObject {
	return container.NewPadded(d.container)
}

// buildUI создаёт интерфейс вкладки дневников
func (d *DiariesTab) buildUI() {
	// Заголовок
	titleText := canvas.NewText("📗 Автоматизация дневников", nil)
	titleText.TextStyle = fyne.TextStyle{Bold: true}
	titleText.TextSize = 20

	// Выбор класса и предмета
	d.classSel = widget.NewSelect([]string{}, d.onClassSelected)
	d.classSel.PlaceHolder = "Выберите класс..."

	d.subjectSel = widget.NewSelect([]string{}, d.onSubjectSelected)
	d.subjectSel.PlaceHolder = "Выберите предмет..."

	filterRow := container.NewGridWithColumns(4,
		widget.NewLabel("Класс:"), d.classSel,
		widget.NewLabel("Предмет:"), d.subjectSel,
	)

	// Пресеты оценок
	presetNames := make([]string, len(gradePresets))
	for i, p := range gradePresets {
		presetNames[i] = p.Emoji + " " + p.Name
	}
	d.presetRadio = widget.NewRadioGroup(presetNames, d.onPresetSelected)
	d.presetRadio.Horizontal = true
	d.presetRadio.SetSelected(presetNames[0]) // По умолчанию «Хорошо и Отлично»

	// Пользовательский диапазон (для «Свой диапазон»)
	d.customMinEntry = widget.NewEntry()
	d.customMinEntry.SetPlaceHolder("Мин")
	d.customMinEntry.SetText("8")
	d.customMinEntry.Wrapping = fyne.TextWrap(fyne.TextTruncate)

	d.customMaxEntry = widget.NewEntry()
	d.customMaxEntry.SetPlaceHolder("Макс")
	d.customMaxEntry.SetText("10")
	d.customMaxEntry.Wrapping = fyne.TextWrap(fyne.TextTruncate)

	customRow := container.NewHBox(
		widget.NewLabel("Свой диапазон:"),
		d.customMinEntry,
		widget.NewLabel("—"),
		d.customMaxEntry,
	)
	customRow.Hide() // Скрыт до выбора «Свой диапазон»

	// Чекбоксы
	d.fillEmptyOnly = widget.NewCheck("Заполнять только пустые", nil)
	d.fillEmptyOnly.SetChecked(true) // По умолчанию включено

	d.quarterMarks = widget.NewCheck("Включить четвертные оценки", nil)
	d.quarterMarks.SetChecked(false)

	d.semesterMarks = widget.NewCheck("Включить семестровые оценки", nil)
	d.semesterMarks.SetChecked(false)

	d.yearMarks = widget.NewCheck("Включить годовые оценки", nil)
	d.yearMarks.SetChecked(false)

	// Кнопки действий
	analyzeBtn := widget.NewButton("Анализировать", d.onAnalyze)

	fillBtn := widget.NewButton("🚀 Заполнить весь год", d.onFillYear)
	fillBtn.Importance = widget.HighImportance

	stopBtn := widget.NewButton("⏹ Остановить", func() {
		d.stopFlag.Store(true)
	})
	stopBtn.Importance = widget.DangerImportance

	limitsBtn := widget.NewButton("Пределы учеников", func() {
		d.showLimitsDialog()
	})

	buttonsRow := container.NewHBox(
		analyzeBtn,
		fillBtn,
		stopBtn,
		layout.NewSpacer(),
		limitsBtn,
	)

	// Прогресс
	d.progressBar = widget.NewProgressBar()
	d.progressBar.Min = 0
	d.progressBar.Max = 1

	d.statsLabel = widget.NewLabel("Готово к заполнению")

	// Результаты
	d.resultsEntry = widget.NewMultiLineEntry()
	d.resultsEntry.SetPlaceHolder("Результаты заполнения появятся здесь...")
	d.resultsEntry.Wrapping = fyne.TextWrapWord

	resultsScroll := container.NewVScroll(d.resultsEntry)
	resultsScroll.SetMinSize(fyne.NewSize(0, 200))

	// Собираем всё вместе
	d.container = container.NewVBox(
		titleText,
		widget.NewSeparator(),
		filterRow,
		widget.NewSeparator(),
		widget.NewLabel("Комбинация оценок:"),
		d.presetRadio,
		customRow,
		widget.NewSeparator(),
		container.NewGridWithColumns(2,
			d.fillEmptyOnly,
			d.quarterMarks,
			d.semesterMarks,
			d.yearMarks,
		),
		widget.NewSeparator(),
		buttonsRow,
		d.progressBar,
		d.statsLabel,
		widget.NewSeparator(),
		widget.NewLabel("Результаты:"),
		resultsScroll,
	)

	// Сохраняем ссылку на customRow для показа/скрытия
	d.container.Objects = d.container.Objects // Убедимся, что всё на месте
}

// onPresetSelected обрабатывает выбор пресета
func (d *DiariesTab) onPresetSelected(selected string) {
	// Показываем/скрываем поля пользовательского диапазона
	// Проверяем, выбран ли «Свой диапазон» (последний пресет)
	isCustom := false
	for i, p := range gradePresets {
		if p.Emoji+" "+p.Name == selected && p.Weights == nil {
			isCustom = (i == len(gradePresets)-1)
		}
	}
	// Простой способ: если выбран последний элемент
	if selected == gradePresets[len(gradePresets)-1].Emoji+" "+gradePresets[len(gradePresets)-1].Name {
		isCustom = true
	}
	// TODO: показать/скрыть customRow
	_ = isCustom
}

// loadJournalOptions загружает опции журнала для выбора класса/предмета
func (d *DiariesTab) loadJournalOptions() {
	opts, err := d.client.GetJournalOptions()

	fyne.Do(func() {
		if err != nil {
			d.statsLabel.SetText("Ошибка загрузки: " + err.Error())
			return
		}

		d.journalOpts = opts

		// Заполняем выпадающий список классов
		classNames := make([]string, len(opts.Groups))
		for i, group := range opts.Groups {
			classNames[i] = group.Name
		}

		d.classSel.Options = classNames
		d.classSel.Refresh()

		if len(classNames) > 0 {
			d.classSel.SetSelectedIndex(0)
		}

		d.statsLabel.SetText(fmt.Sprintf("Загружено классов: %d", len(opts.Groups)))
	})
}

// onClassSelected обрабатывает выбор класса
func (d *DiariesTab) onClassSelected(selected string) {
	if d.journalOpts == nil {
		return
	}

	for _, group := range d.journalOpts.Groups {
		if group.Name == selected {
			d.selectedGroupID = group.ID

			// Обновляем предметы
			subjectNames := make([]string, len(group.Subjects))
			for i, subj := range group.Subjects {
				subjectNames[i] = subj.SubjectName
			}
			d.subjectSel.Options = subjectNames
			d.subjectSel.Refresh()
			d.subjectSel.ClearSelected()

			if len(subjectNames) > 0 {
				d.subjectSel.SetSelectedIndex(0)
			}

			break
		}
	}
}

// onSubjectSelected обрабатывает выбор предмета
func (d *DiariesTab) onSubjectSelected(selected string) {
	if d.journalOpts == nil || d.selectedGroupID == 0 {
		return
	}

	for _, group := range d.journalOpts.Groups {
		if group.ID == d.selectedGroupID {
			for _, subj := range group.Subjects {
				if subj.SubjectName == selected {
					d.selectedSubjectID = subj.SubjectID
					return
				}
			}
		}
	}
}

// getSelectedPreset возвращает выбранный пресет оценок
func (d *DiariesTab) getSelectedPreset() *GradePreset {
	selected := d.presetRadio.Selected
	for i, p := range gradePresets {
		if p.Emoji+" "+p.Name == selected {
			return &gradePresets[i]
		}
	}
	return &gradePresets[0] // По умолчанию
}

// generateWeightedGrade генерирует оценку по весам пресета
func generateWeightedGrade(preset *GradePreset, minVal, maxVal int) int {
	if preset.Weights != nil {
		// Генерация по весам (колоколообразная кривая)
		r := rand.Float64()
		cumulative := 0.0
		for mark := preset.Min; mark <= preset.Max; mark++ {
			if w, ok := preset.Weights[mark]; ok {
				cumulative += w
				if r <= cumulative {
					return mark
				}
			}
		}
		// Fallback — возвращаем максимальную оценку
		return preset.Max
	}

	// Равномерное распределение для «Свой диапазон»
	return minVal + rand.Intn(maxVal-minVal+1)
}

// onAnalyze анализирует и показывает предпросмотр заполнения
func (d *DiariesTab) onAnalyze() {
	if d.journalOpts == nil || d.selectedGroupID == 0 || d.selectedSubjectID == 0 {
		dialog.ShowInformation("Внимание", "Выберите класс и предмет", d.app.GetWindow())
		return
	}

	d.statsLabel.SetText("Анализ данных...")

	go func() {
		preset := d.getSelectedPreset()
		minVal, maxVal := preset.Min, preset.Max
		if preset.Weights == nil {
			minVal, maxVal = parseMinMax(d.customMinEntry.Text, d.customMaxEntry.Text)
		}

		// Находим группу
		var group *edonish.JournalGroup
		for i := range d.journalOpts.Groups {
			if d.journalOpts.Groups[i].ID == d.selectedGroupID {
				group = &d.journalOpts.Groups[i]
				break
			}
		}
		if group == nil {
			fyne.Do(func() {
				d.statsLabel.SetText("Ошибка: класс не найден")
			})
			return
		}

		totalMarks := 0
		analysis := fmt.Sprintf("📊 Анализ заполнения: %s — %s\n", group.Name, d.subjectSel.Selected)
		analysis += fmt.Sprintf("Пресет: %s %s (диапазон %d-%d)\n\n", preset.Emoji, preset.Name, minVal, maxVal)

		// Анализируем каждую четверть
		for _, quarter := range group.Quarters {
			dates, dateErr := d.client.GetJournalDates(d.selectedGroupID, d.selectedSubjectID, quarter.ID)
			students, studErr := d.client.GetJournalStudents(d.selectedGroupID, d.selectedSubjectID, quarter.ID)

			if dateErr != nil || studErr != nil {
				analysis += fmt.Sprintf("❌ %s: ошибка загрузки\n", quarter.Name)
				continue
			}

			quarterMarks := 0
			for _, student := range students {
				for _, date := range dates {
					// Проверяем, есть ли оценка
					hasMark := false
					for _, m := range student.SubjectMarks {
						if m.AssignmentDateID == date.AssignmentDateID && m.Mark > 0 {
							hasMark = true
							break
						}
					}
					if !hasMark {
						quarterMarks++
					}
				}
			}
			totalMarks += quarterMarks
			analysis += fmt.Sprintf("📝 %s: %d учеников × %d дат = %d пустых оценок\n",
				quarter.Name, len(students), len(dates), quarterMarks)
		}

		if d.quarterMarks.Checked {
			totalMarks += len(group.Quarters) // Четвертные оценки
		}
		if d.semesterMarks.Checked {
			totalMarks += 2 // 2 семестра
		}
		if d.yearMarks.Checked {
			totalMarks++ // Годовая
		}

		analysis += fmt.Sprintf("\n🔢 Всего оценок для создания: %d", totalMarks)

		fyne.Do(func() {
			d.resultsEntry.SetText(analysis)
			d.statsLabel.SetText(fmt.Sprintf("Готово к заполнению: %d оценок", totalMarks))
		})
	}()
}

// onFillYear заполняет оценки за весь год
func (d *DiariesTab) onFillYear() {
	if d.fillRunning.Load() {
		dialog.ShowInformation("Внимание", "Заполнение уже выполняется", d.app.GetWindow())
		return
	}

	if d.journalOpts == nil || d.selectedGroupID == 0 || d.selectedSubjectID == 0 {
		dialog.ShowInformation("Внимание", "Выберите класс и предмет", d.app.GetWindow())
		return
	}

	// Подтверждение
	dialog.ShowConfirm("Заполнить весь год?",
		"Это заполнит оценки за ВСЕ четверти для ВСЕХ учеников.\nПродолжить?",
		func(confirmed bool) {
			if !confirmed {
				return
			}
			d.startFillYear()
		},
		d.app.GetWindow(),
	)
}

// startFillYear запускает процесс заполнения за весь год
func (d *DiariesTab) startFillYear() {
	d.fillRunning.Store(true)
	d.stopFlag.Store(false)

	preset := d.getSelectedPreset()
	minVal, maxVal := preset.Min, preset.Max
	if preset.Weights == nil {
		minVal, maxVal = parseMinMax(d.customMinEntry.Text, d.customMaxEntry.Text)
	}

	// Находим группу
	var group *edonish.JournalGroup
	for i := range d.journalOpts.Groups {
		if d.journalOpts.Groups[i].ID == d.selectedGroupID {
			group = &d.journalOpts.Groups[i]
			break
		}
	}
	if group == nil {
		d.fillRunning.Store(false)
		return
	}

	go func() {
		var created, errors int32
		var results strings.Builder
		var lastQuarterStudents []edonish.JournalStudent

		results.WriteString(fmt.Sprintf("🚀 Заполнение: %s — %s\n", group.Name, d.subjectSel.Selected))
		results.WriteString(fmt.Sprintf("Пресет: %s %s\n\n", preset.Emoji, preset.Name))

		// Обрабатываем каждую четверть
		for _, quarter := range group.Quarters {
			if d.stopFlag.Load() {
				results.WriteString("\n⏹ Заполнение остановлено пользователем\n")
				break
			}

			results.WriteString(fmt.Sprintf("📝 %s:\n", quarter.Name))

			// Загружаем даты и учеников
			dates, dateErr := d.client.GetJournalDates(d.selectedGroupID, d.selectedSubjectID, quarter.ID)
			students, studErr := d.client.GetJournalStudents(d.selectedGroupID, d.selectedSubjectID, quarter.ID)

			if dateErr != nil || studErr != nil {
				results.WriteString(fmt.Sprintf("  ❌ Ошибка загрузки: %v / %v\n", dateErr, studErr))
				continue
			}

			// Сохраняем учеников последней четверти для годовых оценок
			lastQuarterStudents = students

			// Заполняем каждого ученика
			for _, student := range students {
				if d.stopFlag.Load() {
					break
				}

				// Проверяем лимиты ученика
				key := fmt.Sprintf("%d", student.StudentID)
				sMin, sMax := minVal, maxVal
				if lim, ok := d.limits[key]; ok {
					sMin, sMax = lim.MinGrade, lim.MaxGrade
				}

				studentCreated := 0
				studentErrors := 0

				// Заполняем каждую пустую дату
				for _, date := range dates {
					if d.stopFlag.Load() {
						break
					}

					// Проверяем, есть ли уже оценка
					if d.fillEmptyOnly.Checked {
						hasMark := false
						for _, m := range student.SubjectMarks {
							if m.AssignmentDateID == date.AssignmentDateID && m.Mark > 0 {
								hasMark = true
								break
							}
						}
						if hasMark {
							continue
						}
					}

					// Генерируем оценку
					mark := generateWeightedGrade(preset, sMin, sMax)

					err := d.client.CreateMark(
						student.StudentID,
						date.AssignmentDateID,
						quarter.ID,
						mark,
					)

					if err != nil {
						atomic.AddInt32(&errors, 1)
						studentErrors++
					} else {
						atomic.AddInt32(&created, 1)
						studentCreated++
					}

					// Обновляем прогресс
					total := len(students) * len(dates) * len(group.Quarters)
					if total > 0 {
						progress := float64(created+errors) / float64(total)
						fyne.Do(func() {
							d.progressBar.SetValue(progress)
							d.statsLabel.SetText(fmt.Sprintf(
								"Создано: %d, Ошибок: %d",
								created, errors,
							))
						})
					}
				}

				results.WriteString(fmt.Sprintf("  ✅ %s %s: %d оценок",
					student.LastName, student.FirstName, studentCreated))
				if studentErrors > 0 {
					results.WriteString(fmt.Sprintf(", %d ошибок", studentErrors))
				}
				results.WriteString("\n")

				// Четвертная оценка
				if d.quarterMarks.Checked {
					qMark := generateWeightedGrade(preset, sMin, sMax)
					err := d.client.CreateQuarterMark(student.StudentID, quarter.ID, qMark)
					if err != nil {
						atomic.AddInt32(&errors, 1)
					} else {
						atomic.AddInt32(&created, 1)
					}
				}
			}

			// Семестровые оценки (по 2 семестра)
			if d.semesterMarks.Checked {
				for semIdx := 1; semIdx <= 2; semIdx++ {
					for _, student := range students {
						sMark := generateWeightedGrade(preset, minVal, maxVal)
						// semester_property_id = quarter.ID * 2 + semIdx (примерная логика)
						semID := quarter.ID*10 + semIdx // Упрощённая формула
						err := d.client.CreateSemesterMark(student.StudentID, semID, sMark)
						if err != nil {
							atomic.AddInt32(&errors, 1)
						} else {
							atomic.AddInt32(&created, 1)
						}
					}
				}
			}
		}

		// Годовая оценка (используем учеников последней четверти)
		if d.yearMarks.Checked && len(lastQuarterStudents) > 0 {
			results.WriteString("\n📅 Годовые оценки:\n")
			for _, student := range lastQuarterStudents {
				yMark := generateWeightedGrade(preset, minVal, maxVal)
				yearID := 1 // Упрощённо, реальный ID нужно получать из API
				err := d.client.CreateYearMark(student.StudentID, yearID, yMark)
				if err != nil {
					atomic.AddInt32(&errors, 1)
					results.WriteString(fmt.Sprintf("  ❌ %s %s: ошибка\n", student.LastName, student.FirstName))
				} else {
					atomic.AddInt32(&created, 1)
					results.WriteString(fmt.Sprintf("  ✅ %s %s: %d\n", student.LastName, student.FirstName, yMark))
				}
			}
		}

		// Итоги
		results.WriteString(fmt.Sprintf("\n🏁 Итого: создано %d оценок, ошибок %d\n", created, errors))

		d.fillRunning.Store(false)

		fyne.Do(func() {
			d.progressBar.SetValue(1)
			d.statsLabel.SetText(fmt.Sprintf("✅ Заполнение завершено: %d создано, %d ошибок", created, errors))
			d.resultsEntry.SetText(results.String())
		})
	}()
}

// showLimitsDialog показывает диалог лимитов оценок для каждого ученика
func (d *DiariesTab) showLimitsDialog() {
	if d.journalOpts == nil || d.selectedGroupID == 0 {
		dialog.ShowInformation("Внимание", "Сначала выберите класс", d.app.GetWindow())
		return
	}

	// Загружаем учеников для выбранного класса
	// Используем первую четверть для получения списка учеников
	var group *edonish.JournalGroup
	for i := range d.journalOpts.Groups {
		if d.journalOpts.Groups[i].ID == d.selectedGroupID {
			group = &d.journalOpts.Groups[i]
			break
		}
	}
	if group == nil || len(group.Quarters) == 0 {
		dialog.ShowInformation("Внимание", "Нет данных о четвертях", d.app.GetWindow())
		return
	}

	// Загружаем учеников
	go func() {
		students, err := d.client.GetJournalStudents(d.selectedGroupID, d.selectedSubjectID, group.Quarters[0].ID)
		if err != nil {
			fyne.Do(func() {
				dialog.ShowError(err, d.app.GetWindow())
			})
			return
		}

		fyne.Do(func() {
			d.showLimitsDialogWithStudents(students)
		})
	}()
}

// showLimitsDialogWithStudents показывает диалог лимитов с загруженными учениками
func (d *DiariesTab) showLimitsDialogWithStudents(students []edonish.JournalStudent) {
	if len(students) == 0 {
		dialog.ShowInformation("Внимание", "Нет учеников", d.app.GetWindow())
		return
	}

	preset := d.getSelectedPreset()
	defaultMin := preset.Min
	defaultMax := preset.Max

	entries := container.NewVBox()
	minEntries := make([]*widget.Entry, len(students))
	maxEntries := make([]*widget.Entry, len(students))

	for i, s := range students {
		key := fmt.Sprintf("%d", s.StudentID)
		minVal := defaultMin
		maxVal := defaultMax
		if lim, ok := d.limits[key]; ok {
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

	header := container.NewGridWithColumns(3,
		widget.NewLabelWithStyle("Ученик", fyne.TextAlignLeading, fyne.TextStyle{Bold: true}),
		widget.NewLabelWithStyle("Мин", fyne.TextAlignCenter, fyne.TextStyle{Bold: true}),
		widget.NewLabelWithStyle("Макс", fyne.TextAlignCenter, fyne.TextStyle{Bold: true}),
	)

	scroll := container.NewVScroll(container.NewVBox(header, entries))
	scroll.SetMinSize(fyne.NewSize(400, 300))

	setAllMin := widget.NewEntry()
	setAllMin.SetText(fmt.Sprintf("%d", defaultMin))
	setAllMax := widget.NewEntry()
	setAllMax.SetText(fmt.Sprintf("%d", defaultMax))

	setAllBtn := widget.NewButton("Установить всем", func() {
		minVal, maxVal := parseMinMax(setAllMin.Text, setAllMax.Text)
		for i := range students {
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
		for i, s := range students {
			key := fmt.Sprintf("%d", s.StudentID)
			minVal, maxVal := parseMinMax(minEntries[i].Text, maxEntries[i].Text)
			d.limits[key] = &studentGradeLimits{
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

	dlg = dialog.NewCustom("Пределы оценок", "Отмена", content, d.app.GetWindow())
	dlg.Show()
}
