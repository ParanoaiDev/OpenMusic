import QtQuick

// Settings and the listener's statistics. Two columns on a wide window, one on a narrow one.
Item {
    id: page
    readonly property var st: app.stateMap
    readonly property var s: app.settingsMap
    readonly property var stats: st.stats || ({})
    readonly property var cache: st.cache || ({})
    readonly property bool active: st.page === 4
    property real pad: Math.max(40, Math.min(90, width * 0.035))
    readonly property bool wide: width >= 1120
    readonly property real gap: 28
    readonly property real colWidth: wide ? Math.floor((width - pad * 2 - gap) / 2) : width - pad * 2

    Flickable {
        id: flick
        anchors.fill: parent
        contentWidth: width
        contentHeight: Math.max(left.y + left.height, right.y + right.height) + 60
        boundsBehavior: Flickable.StopAtBounds
        interactive: false
        pixelAligned: true

        Column {
            x: page.pad
            y: 34
            Text { text: "Настройки"; color: "white"; font.family: "Inter Display"; font.weight: Font.Black; font.pixelSize: 42 }
            Text { text: "Всё сохраняется само"; color: Qt.rgba(1, 1, 1, 0.5); font.family: "Inter"; font.pixelSize: 14 }
        }

        Column {
            id: left
            x: page.pad
            y: 134
            width: page.colWidth
            spacing: page.gap

            SettingsCard {
                title: "Остров"
                note: page.st.islandAvailable ? "мини-плеер у верхнего края экрана" : "недоступен: нужен пакет layer-shell-qt"
                order: 0
                active: page.active
                IslandDemo { width: parent.width; running: page.active && page.s.island }
                Item { width: 1; height: 8 }
                SettingRow { title: "Остров сверху экрана"; text: "Наведите на него — откроется мини-плеер с обложкой, перемоткой и кнопками"
                             checked: page.s.island; enabled2: page.st.islandAvailable; onToggled: (on) => app.setSetting("island", on) }
                SettingRow { title: "Показывать новый трек"; text: "Остров раскрывается на пару секунд, когда начинается следующий трек"
                             checked: page.s.islandPop; enabled2: page.s.island && page.st.islandAvailable; onToggled: (on) => app.setSetting("islandPop", on) }
                SettingRow { title: "Строка текста песни"; text: "В открытом острове видно, какая строка звучит сейчас"
                             checked: page.s.islandLyrics; enabled2: page.s.island && page.st.islandAvailable
                             onToggled: (on) => app.setSetting("islandLyrics", on) }
                SettingRow { title: "Поверх окон"; text: "Выключено — остров живёт на рабочем столе: окна других приложений закрывают его, и он им не мешает"
                             checked: page.s.islandOverWindows; enabled2: page.s.island && page.st.islandAvailable; last: true
                             onToggled: (on) => app.setSetting("islandOverWindows", on) }
            }

            SettingsCard {
                title: "Воспроизведение"
                order: 1
                active: page.active
                SettingRow { title: "Продолжать с того места"; text: "При запуске вернутся очередь и трек, на котором вы остановились"
                             checked: page.s.resume; onToggled: (on) => app.setSetting("resume", on) }
                Item {
                    width: parent.width
                    height: cacheBox.implicitHeight + 28
                    Column {
                        id: cacheBox
                        y: 16
                        width: parent.width
                        spacing: 10
                        Text { text: "Кэш звука"; color: "white"; font.family: "Inter"; font.pixelSize: 15; font.weight: Font.Medium }
                        Text {
                            width: parent.width
                            wrapMode: Text.WordWrap
                            text: "Скачанные треки включаются сразу и играют без интернета. Занято " + (page.cache.used || "0 МБ") + " из " + (page.cache.limit || "")
                            color: Qt.rgba(1, 1, 1, 0.5); font.family: "Inter"; font.pixelSize: 13
                        }
                        Rectangle {
                            width: parent.width; height: 6; radius: 3
                            color: Qt.rgba(1, 1, 1, 0.1)
                            Rectangle {
                                height: parent.height; radius: 3; color: "#f4f4f4"
                                width: parent.width * (page.cache.share || 0)
                                Behavior on width { NumberAnimation { duration: 600; easing.type: Easing.OutCubic } }
                            }
                        }
                        Item {
                            width: parent.width
                            height: 34
                            Row {
                                spacing: 8
                                Repeater {
                                    model: page.st.cacheChoices
                                    PillButton { text: modelData.title; checked: page.s.cacheMb === modelData.mb; onClicked: app.setSetting("cacheMb", modelData.mb) }
                                }
                            }
                            PillButton { anchors.right: parent.right; text: "Очистить"; onClicked: app.libraryAction("clear-audio", "") }
                        }
                    }
                }
            }

            SettingsCard {
                title: "Система"
                order: 2
                active: page.active
                SettingRow { title: "Значок в трее"; text: "Играть, пауза и переключение треков из панели задач"
                             checked: page.s.tray; onToggled: (on) => app.setSetting("tray", on) }
                SettingRow { title: "Закрывать в трей"; text: "Крестик прячет окно, а музыка играет дальше"
                             checked: page.s.closeToTray; onToggled: (on) => app.setSetting("closeToTray", on) }
                Item {
                    width: parent.width
                    height: Math.max(62, children[0].implicitHeight + 26)
                    Column {
                        anchors.verticalCenter: parent.verticalCenter
                        width: parent.width - 120
                        spacing: 3
                        Text { text: "Медиаклавиши и виджет плеера"; color: "white"; font.family: "Inter"; font.pixelSize: 15; font.weight: Font.Medium }
                        Text { width: parent.width; wrapMode: Text.WordWrap; color: Qt.rgba(1, 1, 1, 0.5); font.family: "Inter"; font.pixelSize: 13
                               text: page.st.mprisOk ? "Клавиши клавиатуры, плеер в панели KDE, экран блокировки и KDE Connect на телефоне"
                                                     : "Система не ответила — клавиши работают только в окне OpenMusic" }
                    }
                    Row {
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 8
                        Rectangle { anchors.verticalCenter: parent.verticalCenter; width: 8; height: 8; radius: 4; color: page.st.mprisOk ? "#5fd38a" : "#e06464" }
                        Text { text: page.st.mprisOk ? "работает" : "нет связи"; color: Qt.rgba(1, 1, 1, 0.7); font.family: "Inter"; font.pixelSize: 13 }
                    }
                    Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Qt.rgba(1, 1, 1, 0.06) }
                }
                Item {
                    width: parent.width
                    height: Math.max(62, children[0].implicitHeight + 26)
                    Column {
                        anchors.verticalCenter: parent.verticalCenter
                        width: parent.width - 150
                        spacing: 3
                        Text { text: "Меню приложений"; color: "white"; font.family: "Inter"; font.pixelSize: 15; font.weight: Font.Medium }
                        Text { width: parent.width; wrapMode: Text.WordWrap; color: Qt.rgba(1, 1, 1, 0.5); font.family: "Inter"; font.pixelSize: 13
                               text: page.st.menuEntry ? "OpenMusic есть в меню и в поиске KDE" : "Чтобы открывать OpenMusic из меню и поиска KDE" }
                    }
                    PillButton { anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                                 text: page.st.menuEntry ? "Обновить" : "Добавить"; primary: !page.st.menuEntry; onClicked: app.addToMenu() }
                }
            }

            SettingsCard {
                title: "Вид"
                order: 3
                active: page.active
                SettingRow { title: "Заставка при запуске"; text: "Логотип и плавное появление окна"
                             checked: page.s.intro; onToggled: (on) => app.setSetting("intro", on) }
                SettingRow { title: "Спокойный фон"; text: "Фон главной, кольцо на экране «Сейчас играет» и полоски острова стоят на месте — меньше нагрузка на компьютер"
                             checked: page.s.calm; last: true; onToggled: (on) => app.setSetting("calm", on) }
            }
        }

        Column {
            id: right
            x: page.wide ? page.pad + page.colWidth + page.gap : page.pad
            y: page.wide ? 134 : left.y + left.height + page.gap
            width: page.colWidth
            spacing: page.gap

            SettingsCard {
                title: "Статистика"
                note: "по тому, что вы слушали в OpenMusic"
                order: 1
                active: page.active
                Text {
                    visible: !!page.stats.empty
                    width: parent.width
                    topPadding: 6; bottomPadding: 10
                    wrapMode: Text.WordWrap
                    text: "Слушайте музыку — здесь появится, сколько и кого вы слушаете."
                    color: Qt.rgba(1, 1, 1, 0.5); font.family: "Inter"; font.pixelSize: 14
                }
                Row {
                    visible: !page.stats.empty
                    width: parent.width
                    spacing: 10
                    topPadding: 6
                    Repeater {
                        model: page.stats.periods || []
                        Rectangle {
                            width: (parent.width - 20) / 3
                            height: 104
                            radius: 18
                            color: Qt.rgba(1, 1, 1, 0.05)
                            Column {
                                x: 16; y: 14
                                width: parent.width - 32
                                spacing: 4
                                Text { text: modelData.title; color: Qt.rgba(1, 1, 1, 0.5); font.family: "Inter"; font.pixelSize: 12; font.weight: Font.DemiBold }
                                Text { width: parent.width; text: modelData.time; elide: Text.ElideRight; color: "white"; font.family: "Inter Display"; font.weight: Font.Bold; font.pixelSize: 22 }
                                Text { width: parent.width; text: modelData.plays; elide: Text.ElideRight; color: Qt.rgba(1, 1, 1, 0.5); font.family: "Inter"; font.pixelSize: 12 }
                                Text { width: parent.width; text: modelData.tracks; elide: Text.ElideRight; color: Qt.rgba(1, 1, 1, 0.5); font.family: "Inter"; font.pixelSize: 12 }
                            }
                        }
                    }
                }
                Text {
                    visible: (page.stats.artists || []).length > 0
                    topPadding: 22; bottomPadding: 6
                    text: "Артисты за 30 дней"
                    color: Qt.rgba(1, 1, 1, 0.6); font.family: "Inter"; font.pixelSize: 14; font.weight: Font.DemiBold
                }
                Repeater {
                    model: page.stats.artists || []
                    Item {
                        width: parent.width
                        height: 54
                        Rectangle { anchors.fill: parent; anchors.leftMargin: -10; anchors.rightMargin: -10; radius: 14
                                    color: Qt.rgba(1, 1, 1, artistArea.containsMouse ? 0.05 : 0); Behavior on color { ColorAnimation { duration: 160 } } }
                        Art { width: 38; height: 38; anchors.verticalCenter: parent.verticalCenter; round: 0.5; source: modelData.picture }
                        Column {
                            x: 52
                            anchors.verticalCenter: parent.verticalCenter
                            width: parent.width - x - 150
                            spacing: 2
                            Text { width: parent.width; text: modelData.name; elide: Text.ElideRight; color: "white"; font.family: "Inter"; font.pixelSize: 14; font.weight: Font.Medium }
                            Text { text: modelData.time + " · " + modelData.plays; color: Qt.rgba(1, 1, 1, 0.5); font.family: "Inter"; font.pixelSize: 12 }
                        }
                        Rectangle {
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            width: 130; height: 6; radius: 3
                            color: Qt.rgba(1, 1, 1, 0.08)
                            Rectangle {
                                height: parent.height; radius: 3; color: Qt.rgba(1, 1, 1, 0.85)
                                width: page.active ? parent.width * modelData.share : 0
                                Behavior on width { NumberAnimation { duration: 900; easing.type: Easing.OutCubic } }
                            }
                        }
                        MouseArea { id: artistArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: app.showArtist(modelData.name) }
                    }
                }
                Text {
                    visible: (page.stats.tracks || []).length > 0
                    topPadding: 18; bottomPadding: 6
                    text: "Треки за 30 дней"
                    color: Qt.rgba(1, 1, 1, 0.6); font.family: "Inter"; font.pixelSize: 14; font.weight: Font.DemiBold
                }
                Repeater {
                    model: page.stats.tracks || []
                    Item {
                        width: parent.width
                        height: 54
                        Art { width: 38; height: 38; anchors.verticalCenter: parent.verticalCenter; round: 0.2; source: modelData.cover }
                        Column {
                            x: 52
                            anchors.verticalCenter: parent.verticalCenter
                            width: parent.width - x - 80
                            spacing: 2
                            Text { width: parent.width; text: modelData.title; elide: Text.ElideRight; color: "white"; font.family: "Inter"; font.pixelSize: 14; font.weight: Font.Medium }
                            Text { width: parent.width; text: modelData.artist; elide: Text.ElideRight; color: Qt.rgba(1, 1, 1, 0.5); font.family: "Inter"; font.pixelSize: 12 }
                        }
                        Text { anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; text: modelData.plays
                               color: Qt.rgba(1, 1, 1, 0.6); font.family: "Inter"; font.pixelSize: 13 }
                    }
                }
                Text {
                    topPadding: 16; bottomPadding: 4
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: "В медиатеке " + (page.stats.library || 0) + "  ·  Мне нравится " + (page.stats.likes || 0) + "  ·  Плейлистов " + (page.stats.playlists || 0)
                    color: Qt.rgba(1, 1, 1, 0.45); font.family: "Inter"; font.pixelSize: 13
                }
            }

            SettingsCard {
                title: "Горячие клавиши"
                order: 2
                active: page.active
                Repeater {
                    model: [["Ctrl + Пробел", "Играть или пауза"], ["Ctrl + →  /  Ctrl + ←", "Следующий и предыдущий трек"],
                            ["Ctrl + ↑  /  Ctrl + ↓", "Громче и тише"], ["Ctrl + L", "Сейчас играет и текст"], ["Ctrl + K", "Поиск"],
                            ["Ctrl + I", "Добавить музыку"], ["Ctrl + O", "Открыть аудиофайл"], ["Ctrl + ,", "Настройки"],
                            ["Медиаклавиши", "Работают, даже когда окно свёрнуто"]]
                    Item {
                        width: parent.width
                        height: 44
                        Text { anchors.verticalCenter: parent.verticalCenter; text: modelData[1]; color: Qt.rgba(1, 1, 1, 0.8); font.family: "Inter"; font.pixelSize: 14 }
                        Rectangle {
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            width: keys.implicitWidth + 20; height: 28; radius: 8
                            color: Qt.rgba(1, 1, 1, 0.07)
                            border.color: Qt.rgba(1, 1, 1, 0.1)
                            Text { id: keys; anchors.centerIn: parent; text: modelData[0]; color: "white"; font.family: "Inter"; font.pixelSize: 12; font.weight: Font.DemiBold }
                        }
                    }
                }
            }
        }
    }
    SmoothWheel { flick: flick }
}
