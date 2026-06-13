// HomeworkTab — вкладка домашних заданий.
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

// HomeworkTab — вкладка домашних заданий
type HomeworkTab struct {
	app       *App            // Ссылка на приложение
	container *fyne.Container // Корневой контейнер
}

// NewHomeworkTab создаёт вкладку домашних заданий
func NewHomeworkTab(app *App) *HomeworkTab {
	h := &HomeworkTab{app: app}
	h.buildUI()
	return h
}

// buildUI создаёт интерфейс вкладки домашних заданий
func (h *HomeworkTab) buildUI() {
	// Заголовок
	titleText := canvas.NewText("📝 Домашние задания", nil)
	titleText.TextStyle = fyne.TextStyle{Bold: true}
	titleText.TextSize = 20

	// Заглушка — сообщение о разработке
	placeholderText := canvas.NewText("Домашние задания — в разработке", nil)
	placeholderText.TextSize = 16
	placeholderText.Color = theme.DisabledColor()

	// Описание
	descText := widget.NewLabel(
		"Вкладка домашних заданий будет доступна в следующей версии " + config.AppName + ".\n" +
			"Здесь будет отображаться список заданий по предметам и датам.",
	)
	descText.Wrapping = fyne.TextWrapWord

	// Простая заглушка с иконкой
	iconLabel := canvas.NewText("📝", nil)
	iconLabel.TextSize = 48

	h.container = container.NewVBox(
		layout.NewSpacer(),
		container.NewHBox(layout.NewSpacer(), iconLabel, layout.NewSpacer()),
		container.NewHBox(layout.NewSpacer(), titleText, layout.NewSpacer()),
		widget.NewSeparator(),
		container.NewHBox(layout.NewSpacer(), placeholderText, layout.NewSpacer()),
		container.NewHBox(layout.NewSpacer(), descText, layout.NewSpacer()),
		layout.NewSpacer(),
	)
}

// Container возвращает корневой контейнер вкладки
func (h *HomeworkTab) Container() fyne.CanvasObject {
	return container.NewPadded(h.container)
}
