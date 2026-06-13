package main

import (
	"edonish-app/client"
	"edonish-app/ui"
	"fyne.io/fyne/v2"
)

// AppController - контроллер приложения
type AppController struct {
	app     fyne.App
	window  fyne.Window
	client  *client.EdonishClient
	login   *ui.LoginScreen
	dashboard *ui.Dashboard
}

// NewAppController создаёт новый контроллер приложения
func NewAppController(a fyne.App) *AppController {
	return &AppController{
		app:    a,
		window: a.NewWindow("Edonish - Электронный дневник"),
	}
}

// Run запускает приложение
func (c *AppController) Run() {
	// Инициализируем клиент
	var err error
	c.client, err = client.NewEdonishClient(
		"https://edonish.tj",      // baseURL - основной URL
		"https://edonish.tj/api/auth/login", // authURL - эндпоинт авторизации
	)
	if err != nil {
		// Показываем критическую ошибку
		c.window.ShowAndRun()
		return
	}

	// Создаём экран входа
	c.login = ui.NewLoginScreen(c.app, c.window, c.client)
	c.login.SetOnLogin(c.onLoginSuccess)

	// Показываем экран входа
	c.login.Show()

	// Запускаем главное событие
	c.app.Run()
}

// onLoginSuccess вызывается при успешной авторизации
func (c *AppController) onLoginSuccess() {
	// Закрываем окно входа и создаём дашборд
	c.window.Close()
	c.window = c.app.NewWindow("Edonish - Дашборд")
	
	c.dashboard = ui.NewDashboard(c.app, c.window, c.client)
	c.dashboard.Show()
}
