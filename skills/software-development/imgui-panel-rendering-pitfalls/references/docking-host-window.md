# ImGui Docking — Host Window Pattern

The exact code pattern for setting up ImGui docking with a fullscreen host window and a first-run default layout.

## The host window

```cpp
// In render_frame(), AFTER ImGui::NewFrame() and BEFORE panel rendering:

{
    ImGuiViewport* viewport = ImGui::GetMainViewport();
    ImGui::SetNextWindowPos(viewport->WorkPos);
    ImGui::SetNextWindowSize(viewport->WorkSize);
    ImGui::SetNextWindowViewport(viewport->ID);

    constexpr ImGuiWindowFlags host_flags =
        ImGuiWindowFlags_NoTitleBar | ImGuiWindowFlags_NoCollapse |
        ImGuiWindowFlags_NoResize | ImGuiWindowFlags_NoMove |
        ImGuiWindowFlags_NoBringToFrontOnFocus | ImGuiWindowFlags_NoNavFocus |
        ImGuiWindowFlags_NoBackground | ImGuiWindowFlags_NoDocking;

    ImGui::PushStyleVar(ImGuiStyleVar_WindowRounding, 0.0f);
    ImGui::PushStyleVar(ImGuiStyleVar_WindowBorderSize, 0.0f);
    ImGui::Begin("##DockSpaceHost", nullptr, host_flags);
    ImGui::PopStyleVar(2);

    ImGuiID dockspace_id = ImGui::GetID("BTQuantMainDockSpace");
    ImGui::DockSpace(dockspace_id, ImVec2(0, 0),
                     ImGuiDockNodeFlags_PassthruCentralNode);

    // ... first-run DockBuilder layout here ...

    ImGui::End();
}

// Now workspace_->render_gui() — panels dock into the space above
```

## Why these flags

- `NoTitleBar` / `NoCollapse` / `NoResize` / `NoMove` — the host window must not be movable or resizable itself; only the dock nodes inside it should be
- `NoBringToFrontOnFocus` — prevents the host from stealing focus when a panel is clicked
- `NoNavFocus` — the host is not focusable for keyboard navigation
- `NoBackground` — the host draws no background, so panels are visible through it
- `NoDocking` — the host cannot be docked INTO itself (paradox prevention)

## First-run default layout via DockBuilder

After `DockSpace()` is called, the dock node exists. Use `DockBuilder` to set up a sensible default on the first frame:

```cpp
static bool default_layout_set = false;
if (!default_layout_set) {
    default_layout_set = true;
    ImGui::DockBuilderRemoveNode(dockspace_id);
    ImGui::DockBuilderAddNode(dockspace_id, ImGuiDockNodeFlags_DockSpace);
    ImGui::DockBuilderSetNodeSize(dockspace_id, viewport->WorkSize);

    // Split into regions
    ImGuiID dock_main = dockspace_id;
    ImGuiID dock_top    = ImGui::DockBuilderSplitNode(dock_main, ImGuiDir_Up,    0.04f, nullptr, &dock_main);
    ImGuiID dock_bottom = ImGui::DockBuilderSplitNode(dock_main, ImGuiDir_Down,  0.25f, nullptr, &dock_main);
    ImGuiID dock_left   = ImGui::DockBuilderSplitNode(dock_main, ImGuiDir_Left,  0.18f, nullptr, &dock_main);
    ImGuiID dock_right  = ImGui::DockBuilderSplitNode(dock_main, ImGuiDir_Right, 0.22f, nullptr, &dock_main);

    // Sub-split the rails
    ImGuiID dock_risk       = ImGui::DockBuilderSplitNode(dock_left, ImGuiDir_Up, 0.33f, nullptr, &dock_left);
    ImGuiID dock_positions  = ImGui::DockBuilderSplitNode(dock_left, ImGuiDir_Up, 0.50f, nullptr, &dock_left);
    // dock_left now holds Orders

    ImGuiID dock_watchlist = ImGui::DockBuilderSplitNode(dock_right, ImGuiDir_Up, 0.40f, nullptr, &dock_right);
    // dock_right now holds Orderbook

    // Assign windows by display title (NOT the full "Title###panel_..." name)
    ImGui::DockBuilderDockWindow("Status", dock_top);
    ImGui::DockBuilderDockWindow("Risk", dock_risk);
    ImGui::DockBuilderDockWindow("Positions", dock_positions);
    ImGui::DockBuilderDockWindow("Orders", dock_left);
    ImGui::DockBuilderDockWindow("Watchlist", dock_watchlist);
    ImGui::DockBuilderDockWindow("BTCUSDT Orderbook", dock_right);
    ImGui::DockBuilderDockWindow("Price Chart", dock_main);
    ImGui::DockBuilderDockWindow("Time & Sales", dock_bottom);

    ImGui::DockBuilderFinish(dockspace_id);
}
```

## Window name matching

Panels must call `ImGui::Begin(title)` where `title` matches what `DockBuilderDockWindow` was called with. If the panel uses `title + "###panel_" + pointer`, the display title is just `title` — ImGui splits on `###`.

```cpp
// Panel internal:
std::string window_title = config_.title + "###panel_" + std::to_string(ptr);
ImGui::Begin(window_title.c_str(), ...);

// DockBuilder assignment:
ImGui::DockBuilderDockWindow(config_.title.c_str(), node);  // matches
```

## Persistence

ImGui saves the dock layout to `imgui.ini` automatically. The `static bool default_layout_set` ensures the builder runs only once (on the first frame). On subsequent runs, ImGui restores the user's arrangement from `imgui.ini`. To force a fresh layout, delete `imgui.ini` before starting.

## Common failure modes

- **DockSpace never called** — `ImGuiConfigFlags_DockingEnable` is set but `DockSpace()` is not called. Panels float at default positions. Fix: call `DockSpace()` in the render frame.
- **DockBuilder runs but no panels dock** — window names don't match. Check the panel's `Begin()` title vs the `DockBuilderDockWindow` argument.
- **Host window covers panels** — host is missing `NoBackground` flag or `SetNextWindowSize` doesn't match viewport size.
- **Panels can't be moved** — panel `Begin()` has `ImGuiWindowFlags_NoMove`. Check the panel's window flags.
