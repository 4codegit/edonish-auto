package ui

import (
	"context"
	"edonish-app/client"
	"fmt"
	"time"

	"fyne.io/fyne/v2"
	"fyne.io/fyne/v2/container"
	"fyne.io/fyne/v2/dialog"
	"fyne.io/fyne/v2/widget"
)

// Dashboard - главное окно после авторизации
type Dashboard struct {
	app    fyne.App
	window fyne.Window
	client *client.EdonishClient

	scheduleTab *widget.TabItem
	gradesTab   *widget.TabItem
	homeworkTab *widget.TabItem

	tabs *widget.TabContainer
}

// NewDashboard создаёт новый дашборд
func NewDashboard(app fyne.App, win fyne.Window, cli *client.EdonishClient) *Dashboard {
	return &Dashboard{
		app:    app,
		window: win,
		client: cli,
	}
}

// Show отображает дашборд
func (d *Dashboard) Show() {
	// Создаём вкладки
	d.scheduleTab = widget.NewTabItem("Расписание", widget.NewLabel("Загрузка..."))
	d.gradesTab = widget.NewTabItem("Оценки", widget.NewLabel("Загрузка..."))
	d.homeworkTab = widget.NewTabItem("Домашние задания", widget.NewLabel("Загрузка..."))

	d.tabs = widget.NewTabContainer(
		d.scheduleTab,
		d.gradesTab,
		d.homeworkTab,
	)

	// Устанавливаем содержимое окна
	d.window.SetContent(d.tabs)
	d.window.Resize(fyne.NewSize(1000, 700))

	// Загружаем данные для всех вкладок
	go d.loadAllData()

	d.window.Show()
}

// loadAllData загружает данные для всех вкладок
func (d *Dashboard) loadAllData() {
	// Загружаем расписание
	go d.loadSchedule()
	// Загружаем оценки
	go d.loadGrades()
	// Загружаем домашние задания
	go d.loadHomeworks()
}

// loadSchedule загружает расписание
func (d *Dashboard) loadSchedule() {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	// Получаем расписание на текущую неделю
	// TODO: Настройте формат даты
	schedule, err := d.client.GetSchedule(ctx, "2024-01-01", "2024-12-31")

	fyne.Do(func() {
		if err != nil {
			d.scheduleTab.Content = widget.NewLabel(fmt.Sprintf("Ошибка загрузки: %v", err))
			return
		}

		if len(schedule) == 0 {
			d.scheduleTab.Content = widget.NewLabel("Расписание не найдено")
			return
		}

		// Создаём таблицу для расписания
		table := widget.NewTable(
			func() (int, int) {
				return len(schedule) + 1, 6
			},
			func() fyne.CanvasObject {
				return widget.NewLabel("")
			},
			func(row, col int) fyne.CanvasObject {
				label := widget.NewLabel("")
				switch col {
				case 0:
					label.SetText("Дата")
				case 1:
					label.SetText("Предмет")
				case 2:
					label.SetText("Время")
				case 3:
					label.SetText("Кабинет")
				case 4:
					label.SetText("Учитель")
				case 5:
					label.SetText("ID")
				}
				return label
			}
		)

		// Заполняем данные
		table.SetCellProvider(func(row, col int) string {
			if row == 0 {
				// Заголовки
				headers := []string{"Дата", "Предмет", "Время", "Кабинет", "Учитель", "ID"}
				return headers[col]
			}
			entry := schedule[row-1]
			switch col {
			case 0:
				return entry.Date
			case 1:
				return entry.Subject
			case 2:
				return fmt.Sprintf("%s - %s", entry.StartTime, entry.EndTime)
			case 3:
				return entry.Classroom
			case 4:
				return entry.Teacher
			case 5:
				return fmt.Sprintf("%d", entry.ID)
			}
			return ""
		})

		d.scheduleTab.Content = container.NewVBox(
			widget.NewLabel("Расписание"),
			table,
		)
	})
}

// loadGrades загружает оценки
func (d *Dashboard) loadGrades() {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	// Получаем все оценки
	grades, err := d.client.GetGrades(ctx, "")

	fyne.Do(func() {
		if err != nil {
			d.gradesTab.Content = widget.NewLabel(fmt.Sprintf("Ошибка загрузки: %v", err))
			return
		}

		if len(grades) == 0 {
			d.gradesTab.Content = widget.NewLabel("Оценки не найдены")
			return
		}

		// Создаём таблицу для оценок
		table := widget.NewTable(
			func() (int, int) {
				return len(grades) + 1, 6
			},
			func() fyne.CanvasObject {
				return widget.NewLabel("")
			},
			func(row, col int) fyne.CanvasObject {
				label := widget.NewLabel("")
				switch col {
				case 0:
					label.SetText("Предмет")
				case 1:
					label.SetText("Оценка")
				case 2:
					label.SetText("Дата")
				case 3:
					label.SetText("Учитель")
				case 4:
					label.SetText("Тип")
				case 5:
					label.SetText("Вес")
				}
				return label
			}
		)

		// Заполняем данные
		table.SetCellProvider(func(row, col int) string {
			if row == 0 {
				headers := []string{"Предмет", "Оценка", "Дата", "Учитель", "Тип", "Вес"}
				return headers[col]
			}
			grade := grades[row-1]
			switch col {
			case 0:
				return grade.Subject
			case 1:
				return grade.Value
			case 2:
				return grade.Date
			case 3:
				return grade.Teacher
			case 4:
				return grade.GradeType
			case 5:
				return fmt.Sprintf("%.2f", grade.Weight)
			}
			return ""
		})

		d.gradesTab.Content = container.NewVBox(
			widget.NewLabel("Оценки"),
			table,
		)
	})
}

// loadHomeworks загружает домашние задания
func (d *Dashboard) loadHomeworks() {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	homeworks, err := d.client.GetHomeworks(ctx)

	fyne.Do(func() {
		if err != nil {
			d.homeworkTab.Content = widget.NewLabel(fmt.Sprintf("Ошибка загрузки: %v", err))
			return
		}

		if len(homeworks) == 0 {
			d.homeworkTab.Content = widget.NewLabel("Домашние задания не найдены")
			return
		}

		// Создаём таблицу для домашних заданий
		table := widget.NewTable(
			func() (int, int) {
				return len(homeworks) + 1, 5
			},
			func() fyne.CanvasObject {
				return widget.NewLabel("")
			},
			func(row, col int) fyne.CanvasObject {
				label := widget.NewLabel("")
				switch col {
				case 0:
					label.SetText("Предмет")
				case 1:
					label.SetText("Описание")
				case 2:
					label.SetText("Срок")
				case 3:
					label.SetText("Учитель")
				case 4:
					label.SetText("ID")
				}
				return label
			}
		)

		// Заполняем данные
		table.SetCellProvider(func(row, col int) string {
			if row == 0 {
				headers := []string{"Предмет", "Описание", "Срок", "Учитель", "ID"}
				return headers[col]
			}
			hw := homeworks[row-1]
			switch col {
			case 0:
				return hw.Subject
			case 1:
				// Обрезаем длинное описание
				desc := hw.Description
				if len(desc) > 50 {
					desc = desc[:50] + "..."
				}
				return desc
			case 2:
				return hw.DueDate
			case 3:
				return hw.Teacher
			case 4:
				return fmt.Sprintf("%d", hw.ID)
			}
			return ""
		})

		d.homeworkTab.Content = container.NewVBox(
			widget.NewLabel("Домашние задания"),
			table,
		)
	})
}

// RefreshData обновляет данные на всех вкладках
func (d *Dashboard) RefreshData() {
	d.loadAllData()
}
