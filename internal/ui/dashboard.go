// Dashboard — главная панель приложения с вкладками.
// Отображает информацию о пользователе, кнопки управления и вкладки:
// Оценки, Расписание, ДЗ, Дневники.
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

// Dashboard — главная панель с вкладками
type Dashboard struct {
	app       *App               // Ссылка на приложение
	container *fyne.Container    // Корневой контейнер
	tabs      *container.AppTabs // Вкладки
}

// NewDashboard создаёт главную панель с вкладками
func NewDashboard(app *App) *Dashboard {
	d := &Dashboard{app: app}

	// Создаём вкладки
	gradesTab := NewGradesTab(app)
	scheduleTab := NewScheduleTab(app)
	homeworkTab := NewHomeworkTab(app)
	diariesTab := NewDiariesTab(app)

	d.tabs = container.NewAppTabs(
		container.NewTabItem("📋 Оценки", gradesTab.Container()),
		container.NewTabItem("📅 Расписание", scheduleTab.Container()),
		container.NewTabItem("📝 ДЗ", homeworkTab.Container()),
		container.NewTabItem("📗 Дневники", diariesTab.Container()),
	)

	// Заголовок с информацией о пользователе
	header := d.createHeader()

	// Основной контейнер: заголовок + вкладки
	d.container = container.NewBorder(
		header, // сверху
		nil,    // снизу
		nil,    // слева
		nil,    // справа
		d.tabs, // центр
	)

	return d
}

// createHeader создаёт верхнюю панель с информацией о пользователе
func (d *Dashboard) createHeader() *fyne.Container {
	// Информация о пользователе
	userInfo := d.app.client.UserInfo
	userText := ""
	if userInfo != nil {
		userText = userInfo.FullName()
	}

	roleText := d.app.client.Role
	schoolName := ""
	for _, school := range d.app.client.Schools {
		if school.SchoolID == d.app.client.SchoolID {
			schoolName = school.SchoolName
			break
		}
	}

	// Текст пользователя
	userLabel := canvas.NewText(userText, nil)
	userLabel.TextStyle = fyne.TextStyle{Bold: true}
	userLabel.TextSize = 16

	roleLabel := canvas.NewText(roleText+" — "+schoolName, nil)
	roleLabel.TextSize = 12
	roleLabel.Color = theme.DisabledColor()

	// Кнопка смены темы
	themeBtn := widget.NewButtonWithIcon("", theme.ColorIcon(), d.app.ToggleTheme)
	themeBtn.Importance = widget.LowImportance

	// Кнопка выхода
	logoutBtn := widget.NewButton("Выйти", func() {
		d.app.Logout()
	})
	logoutBtn.Importance = widget.DangerImportance

	// Версия приложения
	versionLabel := canvas.NewText(config.AppName+" v"+config.AppVersion, nil)
	versionLabel.TextSize = 10
	versionLabel.Color = theme.DisabledColor()

	// Левая часть: информация о пользователе
	leftBox := container.NewVBox(userLabel, roleLabel)

	// Правая часть: кнопки и версия
	rightBox := container.NewHBox(
		versionLabel,
		layout.NewSpacer(),
		themeBtn,
		logoutBtn,
	)

	// Заголовок в рамке
	headerContent := container.NewBorder(
		nil, nil,
		leftBox,
		rightBox,
		nil,
	)

	return container.NewPadded(headerContent)
}

// Container возвращает корневой контейнер дашборда
func (d *Dashboard) Container() fyne.CanvasObject {
	return d.container
}
