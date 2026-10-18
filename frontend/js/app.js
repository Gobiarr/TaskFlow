
const telegram = window.Telegram?.WebApp;

if (telegram) {
    telegram.ready();
    telegram.expand();
}

const $ = (selector) => document.querySelector(selector);

const taskList = $("#task-list");
const taskForm = $("#task-form");
const createTaskButton = $("#create-task");
const cancelTaskButton = $("#cancel-task");
const saveTaskButton = $("#save-task");
const titleInput = $("#task-title");
const descriptionInput = $("#task-description");
const totalCount = $("#total-count");
const completedCount = $("#completed-count");
const errorMessage = $("#error-message");

const levelBadge = $(".level-badge");
const xpHeading = $(".xp-card h2");
const xpValue = $(".xp-value");
const xpProgress = $("#xp-progress");

const achievementsList = $("#achievements-list");
const achievementCounter = $("#achievement-counter");
const achievementSummaryTitle = $("#achievement-summary-title");
const achievementSummaryText = $("#achievement-summary-text");
const achievementProgress = $("#achievement-progress");
const achievementError = $("#achievement-error");

const habitList = $("#habits-list");
const habitForm = $("#habit-form");
const createHabitButton = $("#create-habit");
const cancelHabitButton = $("#cancel-habit");
const saveHabitButton = $("#save-habit");
const habitTitleInput = $("#habit-title");
const habitDescriptionInput = $("#habit-description");
const habitError = $("#habit-error");
const habitTotal = $("#habit-total");
const habitDone = $("#habit-done");
const habitCompletions = $("#habit-completions");

const profileLevelBadge = $("#profile-level-badge");
const profileXp = $("#profile-xp");
const profileTasks = $("#profile-tasks");
const profileAchievements = $("#profile-achievements");
const profileLevelTitle = $("#profile-level-title");
const profileXpProgress = $("#profile-xp-progress");
const profileProgressCaption = $("#profile-progress-caption");
const profileError = $("#profile-error");

const screens = {
    tasks: $("#tasks-screen"),
    habits: $("#habits-screen"),
    achievements: $("#achievements-screen"),
    profile: $("#profile-screen"),
};

const navItems = document.querySelectorAll(".nav-item");

let tasks = [];
let profile = null;
let achievements = [];
let habits = [];
let activeScreen = "tasks";
let switchingScreen = false;

async function apiRequest(url, options = {}) {
    const response = await fetch(url, {
        ...options,
        headers: {
            "Content-Type": "application/json",
            ...options.headers,
        },
    });

    if (!response.ok) {
        let message = `Ошибка сервера: ${response.status}`;

        try {
            const data = await response.json();

            if (typeof data.detail === "string") {
                message = data.detail;
            } else if (Array.isArray(data.detail)) {
                message = data.detail
                    .map((item) => item.msg || "Некорректные данные")
                    .join(", ");
            }
        } catch {
            // Используем стандартное сообщение.
        }

        throw new Error(message);
    }

    if (response.status === 204) {
        return null;
    }

    return response.json();
}

function showError(element, message) {
    if (!element) return;

    element.textContent = message;
    element.hidden = false;
}

function hideError(element) {
    if (!element) return;

    element.textContent = "";
    element.hidden = true;
}

function setButtonLoading(button, loading, loadingText, normalText) {
    if (!button) return;

    button.disabled = loading;
    button.textContent = loading ? loadingText : normalText;
}

function updateStats() {
    if (totalCount) {
        totalCount.textContent = tasks.length;
    }

    if (completedCount) {
        completedCount.textContent = tasks.filter(
            (task) => task.is_completed
        ).length;
    }
}

function renderProfile() {
    if (!profile) return;

    const level = Number(profile.level ?? 1);
    const xp = Number(profile.xp ?? 0);
    const currentXp = Number(profile.current_level_xp ?? xp % 100);
    const nextXp = Number(profile.next_level_xp ?? 100);

    const percentage = nextXp > 0
        ? Math.min(100, currentXp / nextXp * 100)
        : 0;

    if (levelBadge) {
        levelBadge.textContent = `⭐ Уровень ${level}`;
    }

    if (xpHeading) {
        xpHeading.textContent = `Уровень ${level}`;
    }

    if (xpValue) {
        xpValue.textContent = `${currentXp} / ${nextXp} XP`;
    }

    if (xpProgress) {
        xpProgress.style.width = `${percentage}%`;
    }

    if (profileLevelBadge) {
        profileLevelBadge.textContent = `⭐ Уровень ${level}`;
    }

    if (profileXp) {
        profileXp.textContent = `${xp} XP`;
    }

    if (profileTasks) {
        profileTasks.textContent = profile.completed_tasks ?? 0;
    }

    if (profileLevelTitle) {
        profileLevelTitle.textContent = `Уровень ${level}`;
    }

    if (profileXpProgress) {
        profileXpProgress.style.width = `${percentage}%`;
    }

    if (profileProgressCaption) {
        profileProgressCaption.textContent =
            `${currentXp} / ${nextXp} XP до следующего уровня`;
    }

    if (profileAchievements) {
        profileAchievements.textContent = achievements.filter(
            (achievement) => achievement.unlocked
        ).length;
    }
}

function createTaskElement(task) {
    const item = document.createElement("article");
    item.className = "task-item";

    if (task.is_completed) {
        item.classList.add("completed");
    }

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.className = "task-check";
    checkbox.checked = task.is_completed;
    checkbox.setAttribute("aria-label", "Отметить выполнение задачи");

    checkbox.addEventListener("change", async () => {
        checkbox.disabled = true;
        hideError(errorMessage);

        try {
            await apiRequest(`/api/tasks/${task.id}/complete`, {
                method: "PATCH",
            });

            await refreshData();
        } catch (error) {
            showError(errorMessage, error.message);
            checkbox.checked = task.is_completed;
            checkbox.disabled = false;
        }
    });

    const content = document.createElement("div");
    content.className = "task-content";

    const title = document.createElement("h3");
    title.textContent = task.title;
    content.appendChild(title);

    if (task.description) {
        const description = document.createElement("p");
        description.textContent = task.description;
        content.appendChild(description);
    }

    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "delete-task";
    deleteButton.textContent = "×";
    deleteButton.setAttribute("aria-label", "Удалить задачу");

    deleteButton.addEventListener("click", async () => {
        deleteButton.disabled = true;
        hideError(errorMessage);

        try {
            await apiRequest(`/api/tasks/${task.id}`, {
                method: "DELETE",
            });

            await refreshData();
        } catch (error) {
            showError(errorMessage, error.message);
            deleteButton.disabled = false;
        }
    });

    item.append(checkbox, content, deleteButton);

    return item;
}

function renderTasks() {
    if (!taskList) return;

    taskList.replaceChildren();

    if (tasks.length === 0) {
        const emptyState = document.createElement("div");
        emptyState.className = "empty-state";

        const icon = document.createElement("span");
        icon.textContent = "✨";

        const heading = document.createElement("h3");
        heading.textContent = "Пока нет задач";

        const description = document.createElement("p");
        description.textContent =
            "Создай первую задачу и начни двигаться к цели.";

        emptyState.append(icon, heading, description);
        taskList.appendChild(emptyState);
    } else {
        tasks.forEach((task) => {
            taskList.appendChild(createTaskElement(task));
        });
    }

    updateStats();
}

function renderAchievements() {
    if (
        !achievementsList ||
        !achievementCounter ||
        !achievementProgress ||
        !achievementSummaryTitle ||
        !achievementSummaryText
    ) {
        return;
    }

    const unlockedCount = achievements.filter(
        (achievement) => achievement.unlocked
    ).length;

    achievementCounter.textContent =
        `${unlockedCount} / ${achievements.length}`;

    achievementProgress.style.width = achievements.length
        ? `${unlockedCount / achievements.length * 100}%`
        : "0%";

    if (profileAchievements) {
        profileAchievements.textContent = unlockedCount;
    }

    if (unlockedCount === achievements.length && achievements.length > 0) {
        achievementSummaryTitle.textContent = "Ты собрал все награды! 🎉";
        achievementSummaryText.textContent =
            "Отличная работа! Продолжай ставить новые цели.";
    } else if (unlockedCount > 0) {
        achievementSummaryTitle.textContent = "Отличное начало!";
        achievementSummaryText.textContent =
            `Открыто ${unlockedCount} из ${achievements.length} достижений. Продолжай!`;
    } else {
        achievementSummaryTitle.textContent = "Начни свой путь!";
        achievementSummaryText.textContent =
            "Выполняй задачи и открывай новые награды.";
    }

    achievementsList.replaceChildren();

    if (achievements.length === 0) {
        const message = document.createElement("p");
        message.className = "achievement-loading";
        message.textContent = "Достижения пока не добавлены.";

        achievementsList.appendChild(message);
        return;
    }

    achievements.forEach((achievement, index) => {
        const card = document.createElement("article");

        card.className = `achievement-card ${
            achievement.unlocked ? "unlocked" : "locked"
        }`;

        card.style.animationDelay = `${Math.min(index * 55, 330)}ms`;

        const icon = document.createElement("div");
        icon.className = "achievement-icon";
        icon.textContent = achievement.icon;

        const status = document.createElement("span");
        status.className = "achievement-status";
        status.textContent = achievement.unlocked
            ? "✓ ОТКРЫТО"
            : "🔒 ЗАКРЫТО";

        const title = document.createElement("h3");
        title.textContent = achievement.title;

        const description = document.createElement("p");
        description.textContent = achievement.description;

        card.append(icon, status, title, description);

        if (achievement.unlocked && achievement.unlocked_at) {
            const date = document.createElement("div");
            date.className = "achievement-date";

            const rawDate = achievement.unlocked_at;
            const parsedDate = new Date(
                rawDate.includes("T")
                    ? rawDate
                    : `${rawDate.replace(" ", "T")}Z`
            );

            date.textContent = Number.isNaN(parsedDate.getTime())
                ? "Достижение получено"
                : `Получено: ${parsedDate.toLocaleDateString("ru-RU")}`;

            card.appendChild(date);
        }

        achievementsList.appendChild(card);
    });
}

function habitIsCompletedToday(habit) {
    return Boolean(
        habit.completed_today ??
        habit.is_completed_today ??
        habit.done_today ??
        habit.completedToday ??
        false
    );
}

function getHabitStreak(habit) {
    return Number(
        habit.streak ??
        habit.current_streak ??
        habit.streak_days ??
        habit.currentStreak ??
        0
    );
}

function getHabitCompletions(habit) {
    return Number(
        habit.total_completions ??
        habit.completions_count ??
        habit.completed_count ??
        habit.total_completed ??
        0
    );
}

function renderHabits() {
    if (!habitList) return;

    habitList.replaceChildren();

    const completedToday = habits.filter(habitIsCompletedToday).length;

    const totalCompletions = habits.reduce(
        (sum, habit) => sum + getHabitCompletions(habit),
        0
    );

    if (habitTotal) habitTotal.textContent = habits.length;
    if (habitDone) habitDone.textContent = completedToday;

    if (habitCompletions) {
        habitCompletions.textContent = totalCompletions;
    }

    if (habits.length === 0) {
        const emptyState = document.createElement("div");
        emptyState.className = "empty-state habit-empty-state";

        const icon = document.createElement("span");
        icon.textContent = "🌱";

        const heading = document.createElement("h3");
        heading.textContent = "Время вырастить первую привычку";

        const description = document.createElement("p");
        description.textContent =
            "Добавь небольшую ежедневную цель и постепенно преврати её в привычку.";

        const button = document.createElement("button");
        button.type = "button";
        button.className = "primary-button";
        button.textContent = "Создать привычку";
        button.addEventListener("click", openHabitForm);

        emptyState.append(icon, heading, description, button);
        habitList.appendChild(emptyState);

        return;
    }

    habits.forEach((habit, index) => {
        const completed = habitIsCompletedToday(habit);
        const streak = getHabitStreak(habit);
        const completions = getHabitCompletions(habit);

        const card = document.createElement("article");

        card.className = `habit-card${completed ? " habit-completed" : ""}`;
        card.style.animationDelay = `${Math.min(index * 50, 300)}ms`;

        const top = document.createElement("div");
        top.className = "habit-card-top";

        const icon = document.createElement("div");
        icon.className = "habit-card-icon";
        icon.textContent = completed ? "✅" : "🌱";

        const titleGroup = document.createElement("div");
        titleGroup.className = "habit-title-group";

        const title = document.createElement("h3");
        title.textContent = habit.title;

        const status = document.createElement("span");
        status.className = "habit-status";
        status.textContent = completed
            ? "ВЫПОЛНЕНО СЕГОДНЯ"
            : "ЕЖЕДНЕВНАЯ ЦЕЛЬ";

        titleGroup.append(title, status);
        top.append(icon, titleGroup);

        const deleteButton = document.createElement("button");
        deleteButton.type = "button";
        deleteButton.className = "delete-task habit-delete";
        deleteButton.textContent = "×";
        deleteButton.setAttribute("aria-label", "Удалить привычку");
        deleteButton.title = "Удалить привычку";

        deleteButton.addEventListener("click", async () => {
            const confirmed = window.confirm(
                `Удалить привычку «${habit.title}»?`
            );

            if (!confirmed) return;

            deleteButton.disabled = true;
            hideError(habitError);

            try {
                await apiRequest(`/api/habits/${habit.id}`, {
                    method: "DELETE",
                });

                await refreshData();
            } catch (error) {
                showError(habitError, error.message);
                deleteButton.disabled = false;
            }
        });

        top.appendChild(deleteButton);

        const description = document.createElement("p");
        description.className = "habit-description";
        description.textContent =
            habit.description || "Каждый день — новый шаг вперёд.";

        const metrics = document.createElement("div");
        metrics.className = "habit-metrics";

        const streakMetric = document.createElement("div");
        streakMetric.className = "habit-metric";

        const streakEmoji = document.createElement("span");
        streakEmoji.className = "metric-emoji";
        streakEmoji.textContent = "🔥";

        const streakText = document.createElement("span");
        streakText.className = "metric-text";
        streakText.textContent = `${streak} ${pluralizeDays(streak)} подряд`;

        streakMetric.append(streakEmoji, streakText);

        const totalMetric = document.createElement("div");
        totalMetric.className = "habit-metric";

        const totalEmoji = document.createElement("span");
        totalEmoji.className = "metric-emoji";
        totalEmoji.textContent = "🎯";

        const totalText = document.createElement("span");
        totalText.className = "metric-text";
        totalText.textContent =
            `${completions} ${pluralizeCompletions(completions)}`;

        totalMetric.append(totalEmoji, totalText);
        metrics.append(streakMetric, totalMetric);

        const completeButton = document.createElement("button");
        completeButton.type = "button";
        completeButton.className = "habit-complete-button";
        completeButton.disabled = completed;

        completeButton.textContent = completed
            ? "✓ Сегодня выполнено"
            : "Отметить выполнение · +5 XP";

        completeButton.addEventListener("click", async () => {
            completeButton.disabled = true;
            completeButton.textContent = "Сохраняем...";
            hideError(habitError);

            try {
                await apiRequest(`/api/habits/${habit.id}/complete`, {
                    method: "POST",
                });

                await refreshData();
            } catch (error) {
                showError(habitError, error.message);
                completeButton.disabled = false;
                completeButton.textContent =
                    "Отметить выполнение · +5 XP";
            }
        });

        card.append(top, description, metrics, completeButton);
        habitList.appendChild(card);
    });
}

function pluralizeDays(value) {
    const number = Math.abs(value) % 100;
    const last = number % 10;

    if (number > 10 && number < 20) return "дней";
    if (last > 1 && last < 5) return "дня";
    if (last === 1) return "день";

    return "дней";
}

function pluralizeCompletions(value) {
    const number = Math.abs(value) % 100;
    const last = number % 10;

    if (number > 10 && number < 20) return "выполнений";
    if (last > 1 && last < 5) return "выполнения";
    if (last === 1) return "выполнение";

    return "выполнений";
}

async function refreshData() {
    const [
        loadedTasks,
        loadedProfile,
        loadedAchievements,
        loadedHabits,
    ] = await Promise.all([
        apiRequest("/api/tasks"),
        apiRequest("/api/profile"),
        apiRequest("/api/achievements"),
        apiRequest("/api/habits"),
    ]);

    tasks = loadedTasks;
    profile = loadedProfile;
    achievements = loadedAchievements;
    habits = loadedHabits;

    renderTasks();
    renderProfile();
    renderAchievements();
    renderHabits();
}

async function loadData() {
    hideError(errorMessage);
    hideError(achievementError);
    hideError(habitError);
    hideError(profileError);

    try {
        await refreshData();
    } catch (error) {
        showError(
            errorMessage,
            `Не удалось загрузить данные: ${error.message}`
        );

        showError(
            achievementError,
            "Не удалось загрузить достижения. Проверь соединение с сервером."
        );

        showError(
            habitError,
            `Не удалось загрузить привычки: ${error.message}`
        );

        showError(
            profileError,
            "Не удалось загрузить профиль. Проверь соединение с сервером."
        );
    }
}

function switchScreen(screenName) {
    const nextScreen = screens[screenName];

    if (!nextScreen || switchingScreen) {
        return;
    }

    if (screenName === activeScreen) {
        // Повторное нажатие на активный раздел тоже прокручивает его наверх.
        resetScreenScroll(nextScreen);
        return;
    }

    const previousScreen = screens[activeScreen];

    if (!previousScreen) return;

    switchingScreen = true;

    const movingForward =
        screenOrder(screenName) >= screenOrder(activeScreen);

    // Сбрасываем прокрутку новой страницы до её отображения.
    resetScreenScroll(nextScreen);

    previousScreen.classList.remove("slide-out-left", "slide-out-right");
    nextScreen.classList.remove("slide-out-left", "slide-out-right");

    nextScreen.classList.add("active");
    nextScreen.style.transition = "none";
    nextScreen.style.transform = movingForward
        ? "translateX(9%)"
        : "translateX(-9%)";
    nextScreen.style.opacity = "0";

    nextScreen.setAttribute("aria-hidden", "false");
    nextScreen.inert = false;

    previousScreen.setAttribute("aria-hidden", "true");
    previousScreen.inert = true;

    void nextScreen.offsetWidth;

    nextScreen.style.transition = "";
    nextScreen.style.transform = "";
    nextScreen.style.opacity = "";

    previousScreen.classList.remove("active");
    previousScreen.classList.add(
        movingForward ? "slide-out-left" : "slide-out-right"
    );

    activeScreen = screenName;

    navItems.forEach((item) => {
        const isActive = item.dataset.screen === screenName;

        item.classList.toggle("active", isActive);

        if (isActive) {
            item.setAttribute("aria-current", "page");
        } else {
            item.removeAttribute("aria-current");
        }
    });

    let finished = false;

    const finishTransition = () => {
        if (finished) return;
        finished = true;

        previousScreen.classList.remove("slide-out-left", "slide-out-right");
        previousScreen.style.transition = "";
        previousScreen.style.transform = "";
        previousScreen.style.opacity = "";

        switchingScreen = false;
    };

    nextScreen.addEventListener(
        "transitionend",
        (event) => {
            if (
                event.target === nextScreen &&
                event.propertyName === "transform"
            ) {
                finishTransition();
            }
        },
        { once: true }
    );

    window.setTimeout(finishTransition, 450);
}

function resetScreenScroll(screen) {
    if (!screen) return;

    screen.scrollTop = 0;

    const scrollContainers = screen.querySelectorAll(
        ".screen-scroll, .screen-content, .scroll-container"
    );

    scrollContainers.forEach((container) => {
        container.scrollTop = 0;
    });

    window.scrollTo({
        top: 0,
        left: 0,
        behavior: "instant",
    });
}

function screenOrder(name) {
    return ["tasks", "habits", "achievements", "profile"].indexOf(name);
}

function openHabitForm() {
    hideError(habitError);

    if (!habitForm) return;

    habitForm.hidden = false;

    if (habitTitleInput) {
        habitTitleInput.focus();
    }
}

createTaskButton?.addEventListener("click", () => {
    hideError(errorMessage);

    if (!taskForm) return;

    taskForm.hidden = !taskForm.hidden;

    if (!taskForm.hidden && titleInput) {
        titleInput.focus();
    }
});

cancelTaskButton?.addEventListener("click", () => {
    taskForm?.reset();

    if (taskForm) {
        taskForm.hidden = true;
    }

    hideError(errorMessage);
});

taskForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    hideError(errorMessage);

    const title = titleInput.value.trim();
    const description = descriptionInput.value.trim();

    if (!title) {
        showError(errorMessage, "Введи название задачи.");
        titleInput.focus();
        return;
    }

    setButtonLoading(saveTaskButton, true, "Сохраняем...", "Сохранить");

    try {
        await apiRequest("/api/tasks", {
            method: "POST",
            body: JSON.stringify({ title, description }),
        });

        taskForm.reset();
        taskForm.hidden = true;

        await loadData();
    } catch (error) {
        showError(
            errorMessage,
            `Не удалось сохранить задачу: ${error.message}`
        );
    } finally {
        setButtonLoading(saveTaskButton, false, "Сохраняем...", "Сохранить");
    }
});

createHabitButton?.addEventListener("click", () => {
    if (!habitForm) return;

    if (habitForm.hidden) {
        openHabitForm();
    } else {
        habitForm.hidden = true;
    }
});

cancelHabitButton?.addEventListener("click", () => {
    habitForm?.reset();

    if (habitForm) {
        habitForm.hidden = true;
    }

    hideError(habitError);
});

habitForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    hideError(habitError);

    const title = habitTitleInput.value.trim();
    const description = habitDescriptionInput.value.trim();

    if (!title) {
        showError(habitError, "Введи название привычки.");
        habitTitleInput.focus();
        return;
    }

    setButtonLoading(
        saveHabitButton,
        true,
        "Создаём...",
        "Создать привычку"
    );

    try {
        await apiRequest("/api/habits", {
            method: "POST",
            body: JSON.stringify({ title, description }),
        });

        habitForm.reset();
        habitForm.hidden = true;

        await refreshData();
    } catch (error) {
        showError(
            habitError,
            `Не удалось создать привычку: ${error.message}`
        );
    } finally {
        setButtonLoading(
            saveHabitButton,
            false,
            "Создаём...",
            "Создать привычку"
        );
    }
});

navItems.forEach((item) => {
    item.addEventListener("click", () => {
        switchScreen(item.dataset.screen);
    });
});

// При запуске приложения все страницы начинаются с верхней позиции.
Object.entries(screens).forEach(([name, screen]) => {
    if (!screen) return;

    screen.classList.toggle("active", name === activeScreen);
    screen.setAttribute("aria-hidden", name === activeScreen ? "false" : "true");
    screen.inert = name !== activeScreen;

    resetScreenScroll(screen);
});

navItems.forEach((item) => {
    const isActive = item.dataset.screen === activeScreen;

    item.classList.toggle("active", isActive);

    if (isActive) {
        item.setAttribute("aria-current", "page");
    } else {
        item.removeAttribute("aria-current");
    }
});

loadData();
