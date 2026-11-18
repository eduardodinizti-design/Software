# Achados — API interna do organizador do PPPoker (v228, IL2CPP v31)

Coletado ao vivo com `recon.js` (read-only) em 10/11/2026. Resolvemos tudo por
**nome** via `il2cpp_*` (endereços mudam a cada execução por ASLR — não guardar
endereços, só nomes). Assembly: `PP.Production.PPPoker.dll`.

## A função-chave: organizar em grade já existe pronta

`FloatingWindowFrameManager` é um **singleton** (`get_Instance`) e É o organizador
nativo. Alvos principais (nome(nº params)):

- **`TileTableWindows()`** — organiza TODAS as mesas em grade. É o "auto-organizar".
- `ApplyTile(2)` / `ApplyTileToRegion(6)` — aplica tiling (região = monitor/área).
- `ZoomTiledWindows(1)` — ajusta o tamanho das mesas organizadas.
- `GetActiveTableControllers(1)` — lista os `FloatingWindowController` vivos (1 por mesa).
- `BringTableToFront(1)`, `CloseTableWindow(1)`, `CreateTableWindow(1)`, `DestroyAllTableWindows()`.
- `ClampAllTablesToRegions(1)`, `GetNextWindowPosition()`, `PositionWindowAtTopLeft(2)`.
- `get_IsEnabled()` — se o modo floating-window está ativo.
- `MoveTableGroupBy(1)`, `SetWindowVisualCenter(4)`, `RefreshAutoOrganizeButtonVisible()`.

Cada mesa é um `FloatingWindowController`: `get_TableId`, `get_OpenOrder`/`SwapOpenOrder(2)`,
`ApplySize`, `ToggleMaximize`, `Minimize(1)`/`Restore(1)`, `GetScreenBounds(4)`,
`get_IsMaximized`/`get_IsMinimized`, `get_Scaler` (→ `WindowScaler.SetScale(1)`).

## Leitura de estado (substitui a visão computacional frágil)

`PP.PPPoker.MultiTableManager` (singleton de dados):
- `GetTableCount()`, `GetTableIds()`, `GetTableInfoList(1)`, `GetTableInfoDict()`
- `GetCurrentTableId()`, `IsTableActive(1)`, `ContainsTable(1)`
- `get_IsInMultiTable`, `get_IsShowMultiTable`
- `ChangeTable(3)`, `ChangeToFirstTable(2)`
- `MultiTableViewForPC.ReOrderPages(2)` / `GetOrderPages(1)`

## A janela Windows REAL e interop Win32 (dentro do C#)

Há 1 HWND real (UnityWndClass) controlado por:
- `WindowsTransparentWindow`: `SetWindowPos(7)`, `SetWindowLong(3)`, `GetWindowLong(2)`,
  `SetLayeredWindowAttributes(4)`, `DwmExtendFrameIntoClientArea(2)`, `EnableTransparent`, `SetTopMost(1)`.
- `WindowDragHandler`: `GetActiveWindow`, `GetCursorPos(1)`, `SetWindowPos(7)`, `GetWindowRect(2)`.

## Multi-monitor e tamanho

- `WindowMonitorMover`: `MoveOriginTo(3)`, `SnapTo(6)`, `HasMonitorAt(2)`, `get_HotkeyPressed`
  (há suporte nativo a HOTKEY de mover entre monitores — relevante p/ a frente de hotkeys).
- `ChangeWindowSizePanel.ResizeWindowSize(1)`; `WindowSizeOption`(Width/Height/SizeList).
- Enums/structs: `TileSlot`, `LayoutDirection`, `WindowSizeType`.

## Estratégia do organizador NVT (revisada — muito mais leve)

Não precisamos hookar nem reimplementar layout. Plano:
1. Resolver `FloatingWindowFrameManager.get_Instance()` e chamar `TileTableWindows()`
   (opcional: `ApplyTileToRegion(...)` p/ grade num monitor específico; `ZoomTiledWindows`).
2. Ler mesas por `MultiTableManager.GetTableInfoList` + `GetActiveTableControllers`.
3. Expor no painel do NVT Mesas como "Organizar (interno)" + escolha de monitor/tamanho.
4. Produção: embarcar agente Frida OU DLL própria (precisa toolchain nativo — ainda ausente).

PENDENTE: prototipar a CHAMADA de `TileTableWindows()` (1ª ação que altera estado) —
ver `actions.js`.
