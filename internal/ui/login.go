// LoginPage — страница входа в систему.
// Содержит поля для логина/пароля, чекбокс «Запомнить» и кнопку входа.
// Поддерживает автозаполнение из сохранённой сессии.
package ui

import (
	"fyne.io/fyne/v2"
	"fyne.io/fyne/v2/canvas"
	"fyne.io/fyne/v2/container"
	"fyne.io/fyne/v2/dialog"
	"fyne.io/fyne/v2/layout"
	"fyne.io/fyne/v2/widget"

	"github.com/4codegit/edonish-auto/internal/config"
)

// LoginPage — страница авторизации
type LoginPage struct {
	app        *App            // Ссылка на главное приложение
	container  *fyne.Container // Корневой контейнер страницы
	loginEntry *widget.Entry   // Поле логина
	passEntry  *widget.Entry   // Поле пароля
	remember   *widget.Check   // Чекбокс «Запомнить»
	loginBtn   *widget.Button  // Кнопка «Войти»
	schoolSel  *widget.Select  // Выбор школы (появляется после логина)
}

// NewLoginPage создаёт страницу входа с автозаполнением из сессии
func NewLoginPage(app *App) *LoginPage {
	lp := &LoginPage{app: app}

	// Заголовок приложения
	titleText := canvas.NewText(config.AppName, nil)
	titleText.TextStyle = fyne.TextStyle{Bold: true}
	titleText.TextSize = 28

	// Подзаголовок
	subtitleText := canvas.NewText("Автоматизация электронного журнала edonish.tj", nil)
	subtitleText.TextSize = 14

	// Поле логина
	lp.loginEntry = widget.NewEntry()
	lp.loginEntry.SetPlaceHolder("Введите логин")
	lp.loginEntry.Wrapping = fyne.TextWrap(fyne.TextTruncate)

	// Поле пароля (скрытый ввод)
	lp.passEntry = widget.NewPasswordEntry()
	lp.passEntry.SetPlaceHolder("Введите пароль")

	// Чекбокс «Запомнить меня»
	lp.remember = widget.NewCheck("Запомнить", nil)

	// Кнопка входа
	lp.loginBtn = widget.NewButton("Войти", lp.onLogin)
	lp.loginBtn.Importance = widget.HighImportance

	// Выбор школы (скрыт до успешной авторизации)
	lp.schoolSel = widget.NewSelect([]string{}, lp.onSchoolSelected)
	lp.schoolSel.PlaceHolder = "Выберите школу..."

	// Автозаполнение из сохранённой сессии
	if lp.app.session != nil {
		lp.loginEntry.SetText(lp.app.session.LoginID)
		if lp.app.session.Remember {
			lp.passEntry.SetText(lp.app.session.Password)
			lp.remember.SetChecked(true)
		}
	}

	// Форма входа
	form := container.NewVBox(
		layout.NewSpacer(),
		container.NewHBox(layout.NewSpacer(), titleText, layout.NewSpacer()),
		container.NewHBox(layout.NewSpacer(), subtitleText, layout.NewSpacer()),
		widget.NewSeparator(),
		widget.NewForm(
			&widget.FormItem{Text: "Логин", Widget: lp.loginEntry},
			&widget.FormItem{Text: "Пароль", Widget: lp.passEntry},
		),
		lp.remember,
		lp.loginBtn,
		lp.schoolSel,
		layout.NewSpacer(),
	)

	// Центрируем форму
	lp.container = container.NewPadded(
		container.NewCenter(
			container.NewVBox(
				container.NewHBox(layout.NewSpacer(), form, layout.NewSpacer()),
			),
		),
	)

	return lp
}

// GetLoginEntry возвращает поле ввода логина (для фокуса)
func (lp *LoginPage) GetLoginEntry() *widget.Entry {
	return lp.loginEntry
}

// Container возвращает корневой контейнер страницы (реализация fyne.CanvasObject)
func (lp *LoginPage) Container() fyne.CanvasObject {
	return lp.container
}

// onLogin обрабатывает нажатие кнопки «Войти»
// Выполняет авторизацию и загружает список школ
func (lp *LoginPage) onLogin() {
	login := lp.loginEntry.Text
	password := lp.passEntry.Text

	// Проверяем, что поля заполнены
	if login == "" || password == "" {
		dialog.ShowError(
			&simpleError{"Введите логин и пароль"},
			lp.app.GetWindow(),
		)
		return
	}

	// Блокируем кнопку на время запроса
	lp.loginBtn.Disable()
	lp.loginBtn.SetText("Вход...")

	// Выполняем авторизацию в горутине
	go func() {
		err := lp.app.client.Login(login, password)
		fyne.Do(func() {
			lp.loginBtn.Enable()
			lp.loginBtn.SetText("Войти")

			if err != nil {
				dialog.ShowError(err, lp.app.GetWindow())
				return
			}

			// Загружаем информацию о школах/ролях
			err = lp.app.client.FetchHeaderInfo()
			if err != nil {
				dialog.ShowError(err, lp.app.GetWindow())
				return
			}

			// Показываем выбор школы
			schoolNames := make([]string, len(lp.app.client.Schools))
			for i, school := range lp.app.client.Schools {
				schoolNames[i] = school.SchoolName + " (" + school.Name + ")"
			}
			lp.schoolSel.Options = schoolNames
			lp.schoolSel.Refresh()

			// Если школа одна — выбираем автоматически
			if len(lp.app.client.Schools) == 1 {
				lp.schoolSel.SetSelectedIndex(0)
			}
		})
	}()
}

// onSchoolSelected обрабатывает выбор школы
// Устанавливает роль и переходит к дашборду
func (lp *LoginPage) onSchoolSelected(selected string) {
	if selected == "" {
		return
	}

	// Определяем индекс выбранной школы
	idx := -1
	for i, opt := range lp.schoolSel.Options {
		if opt == selected {
			idx = i
			break
		}
	}

	if idx < 0 || idx >= len(lp.app.client.Schools) {
		return
	}

	school := lp.app.client.Schools[idx]
	err := lp.app.client.SelectSchool(school.SchoolID)
	if err != nil {
		dialog.ShowError(err, lp.app.GetWindow())
		return
	}

	// Сохраняем сессию
	go lp.app.SaveSession(
		lp.loginEntry.Text,
		lp.passEntry.Text,
		school.SchoolID,
		lp.remember.Checked,
	)

	// Переходим на дашборд
	lp.app.ShowDashboard()
}

// simpleError — простая реализация error для отображения в диалогах
type simpleError struct {
	msg string
}

func (e *simpleError) Error() string {
	return e.msg
}
