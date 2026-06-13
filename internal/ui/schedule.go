// ScheduleTab — вкладка расписания.
// В данный момент является заглушкой, будет реализована позже.
package ui

import (
	"fyne.io/fyne/v2"
	"fyne.io/fyne/v2/canvas"
	"fyne.io/fyne/v2/container"
	"fyne.io/fyne/v2/layout"
	"fyne.io/fyne/v2/theme"
	"fyne.io/fyne/v2/widget"

	"github.com/4codegit/edonish-auto/internal/config"
)

// ScheduleTab — вкладка расписания уроков
type ScheduleTab struct {
	app       *App            // Ссылка на приложение
	container *fyne.Container // Корневой контейнер
}

// NewScheduleTab создаёт вкладку расписания
func NewScheduleTab(app *App) *ScheduleTab {
	s := &ScheduleTab{app: app}
	s.buildUI()
	return s
}

// buildUI создаёт интерфейс вкладки расписания
func (s *ScheduleTab) buildUI() {
	// Заголовок
	titleText := canvas.NewText("📅 Расписание", nil)
	titleText.TextStyle = fyne.TextStyle{Bold: true}
	titleText.TextSize = 20

	// Заглушка — сообщение о разработке
	placeholderText := canvas.NewText("Расписание — в разработке", nil)
	placeholderText.TextSize = 16
	placeholderText.Color = theme.DisabledColor()

	// Описание
	descText := widget.NewLabel(
		"Вкладка расписания будет доступна в следующей версии " + config.AppName + ".\n" +
			"Здесь будет отображаться расписание уроков по дням недели.",
	)
	descText.Wrapping = fyne.TextWrapWord

	// Простая таблица-заглушка с днями недели
	days := []string{"Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота"}
	scheduleGrid := container.NewGridWithColumns(len(days))
	for _, day := range days {
		dayLabel := widget.NewLabelWithStyle(day, fyne.TextAlignCenter, fyne.TextStyle{Bold: true})
		scheduleGrid.Add(dayLabel)
	}

	// Добавляем пустые строки для уроков (1-8)
	for hour := 1; hour <= 8; hour++ {
		for _, day := range days {
			cell := widget.NewLabel("—")
			cell.Alignment = fyne.TextAlignCenter
			_ = day // Избегаем предупреждения
			scheduleGrid.Add(cell)
		}
	}

	scheduleScroll := container.NewVScroll(scheduleGrid)
	scheduleScroll.SetMinSize(fyne.NewSize(600, 400))

	s.container = container.NewBorder(
		container.NewVBox(
			titleText,
			widget.NewSeparator(),
			placeholderText,
			descText,
			widget.NewSeparator(),
		),
		nil, nil, nil,
		scheduleScroll,
	)
}

// Container возвращает корневой контейнер вкладки
func (s *ScheduleTab) Container() fyne.CanvasObject {
	return container.NewPadded(s.container)
}
