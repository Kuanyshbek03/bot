let tg = window.Telegram.WebApp;

tg.expand(); // Расширяем Web App
tg.MainButton.textColor = '#FFFFFF';
tg.MainButton.color = '#2cab37';

function wheelOfFortune(selector) {
  const node = document.querySelector(selector);
  if (!node) return;

  const spin = node.querySelector('button');
  const wheel = node.querySelector('ul');
  let animation;
  let previousEndDegree = 0;

  spin.addEventListener('click', () => {
    if (animation) {
      animation.cancel(); // Сбрасываем анимацию, если она уже существует
    }

    const randomAdditionalDegrees = Math.random() * 360 + 1800;
    const newEndDegree = previousEndDegree + randomAdditionalDegrees;

    animation = wheel.animate([
      { transform: `rotate(${previousEndDegree}deg)` },
      { transform: `rotate(${newEndDegree}deg)` }
    ], {
      duration: 4000,
      direction: 'normal',
      easing: 'cubic-bezier(0.440, -0.205, 0.000, 1.130)',
      fill: 'forwards',
      iterations: 1
    });

    animation.onfinish = () => {
      previousEndDegree = newEndDegree % 360;
      const slice = Math.floor((previousEndDegree / 360) * 12); // Получаем номер сегмента
      const discount = [5, 0, 10, 0, 15, 0, 20, 0, 25, 0, 30, 0][slice]; // Массив соответствующих скидок
      
      // Отправляем данные о скидке в Telegram Web App
      tg.MainButton.setText(`Скидка: ${discount}%`);
      tg.MainButton.show();
      
      tg.onEvent('mainButtonClicked', () => {
        tg.sendData(`${discount}`); // Отправляем скидку обратно в бот
      });
    };
  });
}

// Инициализация колеса удачи
wheelOfFortune('.ui-wheel-of-fortune');
