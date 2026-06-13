// Package ui содержит все компоненты пользовательского интерфейса приложения.
// Главный App управляет окном, навигацией между страницами и темой.
package ui

import (
	"encoding/json"
	"os"
	"path/filepath"

	"fyne.io/fyne/v2"
	"fyne.io/fyne/v2/app"
	"fyne.io/fyne/v2/theme"

	"github.com/4codegit/edonish-auto/internal/config"
	"github.com/4codegit/edonish-auto/internal/edonish"
)

// App — главное приложение, управляющее окном и навигацией
type App struct {
	fyneApp    fyne.App               // Приложение Fyne
	mainWindow fyne.Window            // Главное окно
	client     *edonish.EdonishClient // Клиент API
	isDark     bool                   // Тёмная тема включена
	session    *SessionData           // Данные сохранённой сессии
}

// SessionData — данные сессии для сохранения/загрузки
type SessionData struct {
	LoginID  string `json:"login_id"`  // Логин
	Password string `json:"password"`  // Пароль (сохраняется только если запомнить)
	SchoolID int    `json:"school_id"` // ID выбранной школы
	Remember bool   `json:"remember"`  // Флаг «Запомнить»
}

// NewApp создаёт новое приложение eDonish Auto
func NewApp() *App {
	a := &App{
		fyneApp: app.NewWithID(config.AppName),
		client:  edonish.NewEdonishClient(),
		isDark:  true,
	}

	// Настраиваем главное окно
	a.mainWindow = a.fyneApp.NewWindow(config.AppName)
	a.mainWindow.Resize(fyne.NewSize(1200, 800))
	a.mainWindow.CenterOnScreen()

	// Устанавливаем тему
	a.applyTheme()

	// Загружаем сохранённую сессию
	a.session = a.loadSession()

	// Показываем страницу входа
	a.showLogin()

	return a
}

// Run запускает главный цикл приложения
func (a *App) Run() {
	a.mainWindow.ShowAndRun()
}

// applyTheme применяет текущую тему (тёмную/светлую)
func (a *App) applyTheme() {
	if a.isDark {
		a.fyneApp.Settings().SetTheme(theme.DefaultTheme())
	} else {
		a.fyneApp.Settings().SetTheme(theme.DefaultTheme())
	}
}

// ToggleTheme переключает между тёмной и светлой темой
func (a *App) ToggleTheme() {
	a.isDark = !a.isDark
	a.applyTheme()
}

// showLogin отображает страницу входа
func (a *App) showLogin() {
	loginPage := NewLoginPage(a)
	a.mainWindow.SetContent(loginPage.Container())
	a.mainWindow.Canvas().Focus(loginPage.GetLoginEntry())
}

// ShowDashboard отображает главную панель с вкладками после успешного входа
func (a *App) ShowDashboard() {
	dashboard := NewDashboard(a)
	a.mainWindow.SetContent(dashboard.Container())
}

// Logout выходит из системы и возвращается на страницу входа
func (a *App) Logout() {
	// Очищаем данные клиента
	a.client = edonish.NewEdonishClient()
	// Возвращаемся на страницу входа
	a.showLogin()
}

// sessionFilePath возвращает путь к файлу сессии
func sessionFilePath() string {
	home, err := os.UserHomeDir()
	if err != nil {
		return ""
	}
	return filepath.Join(home, config.SessionFile)
}

// loadSession загружает сохранённую сессию из файла
func (a *App) loadSession() *SessionData {
	path := sessionFilePath()
	if path == "" {
		return nil
	}

	data, err := os.ReadFile(path)
	if err != nil {
		return nil
	}

	var session SessionData
	if err := json.Unmarshal(data, &session); err != nil {
		return nil
	}

	return &session
}

// SaveSession сохраняет данные сессии в файл
func (a *App) SaveSession(loginID, password string, schoolID int, remember bool) error {
	session := SessionData{
		LoginID:  loginID,
		SchoolID: schoolID,
		Remember: remember,
	}
	// Сохраняем пароль только если пользователь выбрал «Запомнить»
	if remember {
		session.Password = password
	}

	data, err := json.Marshal(session)
	if err != nil {
		return err
	}

	path := sessionFilePath()
	if path == "" {
		return nil
	}

	return os.WriteFile(path, data, 0600) // Только владелец может читать
}

// GetClient возвращает клиент API
func (a *App) GetClient() *edonish.EdonishClient {
	return a.client
}

// GetWindow возвращает главное окно
func (a *App) GetWindow() fyne.Window {
	return a.mainWindow
}

// IsDark возвращает true если тёмная тема включена
func (a *App) IsDark() bool {
	return a.isDark
}
