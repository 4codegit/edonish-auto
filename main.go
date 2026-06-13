// main.go — точка входа приложения eDonish Auto.
// Создаёт и запускает десктоп-приложение на базе Fyne
// для автоматизации работы с электронным журналом edonish.tj.
package main

import (
	"github.com/4codegit/edonish-auto/internal/ui"
)

func main() {
	// Создаём приложение и запускаем главный цикл
	app := ui.NewApp()
	app.Run()
}
