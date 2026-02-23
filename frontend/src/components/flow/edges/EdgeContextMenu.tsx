import { useState, useEffect, useRef } from 'react'

interface EdgeContextMenuProps {
  x: number
  y: number
  edgeId: string
  edgeType: string
  condition: string
  onClose: () => void
  onDelete: (edgeId: string) => void
  onUpdate: (edgeId: string, updates: { edge_type?: string; condition?: string }) => void
}

export function EdgeContextMenu({
  x,
  y,
  edgeId,
  edgeType,
  condition,
  onClose,
  onDelete,
  onUpdate,
}: EdgeContextMenuProps) {
  const [showConditionInput, setShowConditionInput] = useState(false)
  const [conditionText, setConditionText] = useState(condition)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose()
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [onClose])

  const toggleEdgeType = () => {
    const newType = edgeType === 'solid' ? 'dashed' : 'solid'
    if (newType === 'dashed') {
      setShowConditionInput(true)
    } else {
      onUpdate(edgeId, { edge_type: newType, condition: '' })
    }
  }

  const handleConditionSave = () => {
    onUpdate(edgeId, { edge_type: 'dashed', condition: conditionText })
  }

  return (
    <div
      ref={menuRef}
      className="fixed z-50 bg-gray-800 border border-gray-600 rounded-lg shadow-xl py-1 min-w-[180px]"
      style={{ left: x, top: y }}
    >
      {showConditionInput ? (
        <div className="px-3 py-2 space-y-2">
          <label className="text-xs text-gray-400">条件表达式</label>
          <input
            value={conditionText}
            onChange={e => setConditionText(e.target.value)}
            placeholder="如: uploaded_assets 包含 image"
            className="w-full text-xs bg-gray-900 border border-gray-600 rounded px-2 py-1.5 text-white placeholder:text-gray-500 focus:outline-none focus:border-indigo-500"
            autoFocus
          />
          <div className="flex gap-1.5">
            <button
              onClick={handleConditionSave}
              className="text-[10px] px-2.5 py-1 rounded bg-yellow-600 text-white hover:bg-yellow-500"
            >
              保存
            </button>
            <button
              onClick={() => setShowConditionInput(false)}
              className="text-[10px] px-2.5 py-1 rounded bg-gray-700 text-gray-300 hover:bg-gray-600"
            >
              取消
            </button>
          </div>
        </div>
      ) : (
        <>
          <button
            onClick={toggleEdgeType}
            className="w-full text-left px-3 py-2 text-xs text-gray-200 hover:bg-gray-700 flex items-center gap-2"
          >
            {edgeType === 'solid' ? (
              <>
                <span className="w-4 border-t-2 border-dashed border-yellow-400" />
                设为条件边 (虚线)
              </>
            ) : (
              <>
                <span className="w-4 border-t-2 border-solid border-green-400" />
                设为必经边 (实线)
              </>
            )}
          </button>

          {edgeType === 'dashed' && (
            <button
              onClick={() => setShowConditionInput(true)}
              className="w-full text-left px-3 py-2 text-xs text-gray-200 hover:bg-gray-700"
            >
              编辑条件...
            </button>
          )}

          <div className="border-t border-gray-700 my-1" />

          <button
            onClick={() => onDelete(edgeId)}
            className="w-full text-left px-3 py-2 text-xs text-red-400 hover:bg-gray-700"
          >
            删除连线
          </button>
        </>
      )}
    </div>
  )
}
