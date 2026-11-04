import { lazy } from "react";
import { createBrowserRouter, RouterProvider } from "react-router";
import { AppShell } from "@/components/layout/AppShell";
import { NotFound } from "@/components/NotFound";
import { ContactDetailPage } from "@/features/contacts/ContactDetailPage";
import { ContactsPage } from "@/features/contacts/ContactsPage";
import { InboxPage } from "@/features/inbox/InboxPage";
import { PipelinePage } from "@/features/pipeline/PipelinePage";

// Heavier, less-visited pages load on demand (AppShell wraps the outlet in <Suspense>).
const InsightsPage = lazy(() =>
  import("@/features/insights/InsightsPage").then((m) => ({ default: m.InsightsPage })),
);
const SimulatorPage = lazy(() =>
  import("@/features/simulator/SimulatorPage").then((m) => ({ default: m.SimulatorPage })),
);

const CatalogPage = lazy(() =>
  import("@/features/catalog/CatalogPage").then((m) => ({ default: m.CatalogPage })),
);

const PostsPage = lazy(() => import("@/features/posts/PostsPage").then((m) => ({ default: m.PostsPage })));

const SettingsPage = lazy(() =>
  import("@/features/settings/SettingsPage").then((m) => ({ default: m.SettingsPage })),
);

const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <PipelinePage /> },
      { path: "deals/:dealId", element: <PipelinePage /> },
      { path: "insights", element: <InsightsPage /> },
      { path: "contacts", element: <ContactsPage /> },
      { path: "contacts/:contactId", element: <ContactDetailPage /> },
      { path: "inbox", element: <InboxPage /> },
      { path: "inbox/:conversationId", element: <InboxPage /> },
      { path: "catalog", element: <CatalogPage /> },
      { path: "posts", element: <PostsPage /> },
      { path: "simulator", element: <SimulatorPage /> },
      { path: "settings", element: <SettingsPage /> },
      { path: "*", element: <NotFound /> },
    ],
  },
]);

export function App() {
  return <RouterProvider router={router} />;
}
