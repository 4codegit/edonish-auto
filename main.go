package main

import (
	"fyne.io/fyne/v2/app"
)

// main - точка входа в приложение
func main() {
	// Создаём приложение Fyne
	a := app.New()

	// Создаём контроллер приложения
	ctrl := NewAppController(a)

	// Запускаем приложение
	ctrl.Run()
}
