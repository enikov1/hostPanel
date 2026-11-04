# Замена нативных контролов на кастомные (ui/)

Задача: во всех вью заменить нативные `<select>`, `<input type="checkbox">`,
`<input type="radio">` на кастомные компоненты `src/components/ui/`.
**НЕ трогать**: `<input type="text|number|password|date|file">`, textarea — они остаются.

## Компоненты (прочитайте их код перед работой!)

```ts
import UiSelect from '../components/ui/UiSelect.vue';   // путь скорректируйте по глубине
import UiCheckbox from '../components/ui/UiCheckbox.vue';
import UiRadio from '../components/ui/UiRadio.vue';
import UiRange from '../components/ui/UiRange.vue';     // пока нигде не используется
```

### UiSelect
```html
<UiSelect v-model="x" :options="[{ value: 'a', label: 'Вариант A' }, { value: '', label: 'все' }]"
          @change="onXChange()" :disabled="cond" placeholder="— выберите —" />
```
- `options`: массив `{ value, label, disabled? }`. Значения сравниваются как строки.
- Эмитит `update:modelValue` и `change` (после обновления модели).
- Динамические списки — inline map в шаблоне:
  `:options="codes.map(c => ({ value: c, label: c }))"`
  или computed в script.
- Первую «пустую» опцию (например `<option value="">все</option>`) передавайте
  первым элементом options.

### UiCheckbox
```html
<UiCheckbox v-model="flag">Текст галочки</UiCheckbox>
<UiCheckbox v-model="flag" :disabled="cond">
  <b>Заголовок</b><span class="faint">описание…</span>
</UiCheckbox>
```
- Слот — весь текст/содержимое строки (переносите как есть, включая вложенные
  span/pill). Эмитит только `update:modelValue`; если был `@change="fn()"` —
  используйте `@update:model-value="fn"` (без аргумента или с boolean).
- НЕ переносите `style="margin:0"` со старого label — стили теперь в классе
  `.uicheck`; если нужен отступ — оберните в div или добавьте style на компонент.

### UiRadio (группа: одинаковый name, разные value)
```html
<UiRadio v-model="choice" name="dbtype" value="mysql">MariaDB</UiRadio>
<UiRadio v-model="choice" name="dbtype" value="pg">PostgreSQL</UiRadio>
```

### UiRange
```html
<UiRange v-model="n" :min="0" :max="100" :step="1" />
```

## Типовые случаи из кода

1) Было:
```html
<select v-model="fCode" @change="applyLogFilters()">
  <option value="">все</option>
  <option v-for="c in CODES" :key="c">{{ c }}</option>
</select>
```
Стало:
```html
<UiSelect v-model="fCode" :options="[{ value: '', label: 'все' },
  ...CODES.map(c => ({ value: c, label: c }))]" @change="applyLogFilters()" />
```

2) Было (disabled):
```html
<input type="checkbox" checked disabled> {{ m }}
<span class="pill ok">включён</span>
```
Стало:
```html
<UiCheckbox :model-value="true" :disabled="true">
  {{ m }} <span class="pill ok">включён</span>
</UiCheckbox>
```

3) Радио в DbsView — смотрите контекст и заменяйте на UiRadio group.

## Правила

- v-model сохраняется, поведение не меняется. Все тексты/пилы/описания из
  слота переносятся 1:1.
- @change-обработчики, читавшие `$event.target.value`, перепишите на
  приём значения: `@update:model-value="(v) => fn(String(v))"` — и при
  необходимости поправьте сигнатуру функции в script (разрешено).
- После правок своего файла: `cd C:\hostpanel\web-src && npm run build` —
  чините ТОЛЬКО свои файлы (другие агенты правят остальные параллельно).
- Не редактируйте компоненты ui/* и app.css.
