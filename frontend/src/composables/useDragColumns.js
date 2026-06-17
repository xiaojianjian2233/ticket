// 通用：列表列「拖动调整顺序」+ 顺序持久化（列宽由 el-table border 原生支持拖动）
// 用法：const { reset } = useDragColumns(tableRef, columns, 'ticket-list-cols')
//   - columns: ref([{ key, ... }])，与渲染的可拖动列(.drag-col)一一对应、同序
//   - 仅 label-class-name="drag-col" 的表头列参与拖动；选择列/操作列不加该 class 即排除
import Sortable from 'sortablejs'
import { nextTick, onMounted } from 'vue'

export function useDragColumns(tableRef, columns, storageKey) {
  const defaultKeys = columns.value.map((c) => c.key)

  const applySaved = () => {
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey) || 'null')
      if (Array.isArray(saved) && saved.length) {
        columns.value.sort((a, b) => {
          const ia = saved.indexOf(a.key)
          const ib = saved.indexOf(b.key)
          return (ia < 0 ? 999 : ia) - (ib < 0 ? 999 : ib)
        })
      }
    } catch (e) { /* ignore */ }
  }
  const persist = () => localStorage.setItem(storageKey, JSON.stringify(columns.value.map((c) => c.key)))

  const init = async () => {
    applySaved()
    await nextTick()
    const tr = tableRef.value?.$el?.querySelector('.el-table__header-wrapper thead tr')
    if (!tr) return
    Sortable.create(tr, {
      animation: 150,
      draggable: '.drag-col',
      onEnd: (evt) => {
        const from = evt.oldDraggableIndex
        const to = evt.newDraggableIndex
        if (from == null || to == null || from === to) return
        const arr = columns.value
        const [moved] = arr.splice(from, 1)
        arr.splice(to, 0, moved)
        persist()
      },
    })
  }

  const reset = () => {
    localStorage.removeItem(storageKey)
    columns.value.sort((a, b) => defaultKeys.indexOf(a.key) - defaultKeys.indexOf(b.key))
  }

  onMounted(init)
  return { reset }
}
