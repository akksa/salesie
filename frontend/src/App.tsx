import { createBrowserRouter, Navigate, RouterProvider } from "react-router";
import { AppShell } from "@/components/layout/AppShell";
import { NotFound } from "@/components/NotFound";
import { CatalogPage } from "@/features/catalog/CatalogPage";
import { ContactDetailPage } from "@/features/contacts/ContactDetailPage";
import { ContactsPage } from "@/features/contacts/ContactsPage";
import { InboxPage } from "@/features/inbox/InboxPage";
import { PostsPage } from "@/features/posts/PostsPage";
import { SettingsPage } from "@/features/settings/SettingsPage";
import { SimulatorPage } from "@/features/simulator/SimulatorPage";

const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <Navigate to="/contacts" replace /> },
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
