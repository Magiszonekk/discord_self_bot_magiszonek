"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import { ThemeToggle } from "@/components/theme-toggle";
import {
  checkAuth,
  logout,
  getStatuses,
  addStatus,
  deleteStatus,
  approveStatus,
  revokeStatus,
  getCategories,
  addCategory,
  deleteCategory,
  changeStatus,
  sendDm,
  getDmRecipients,
  getEventSubStatus,
  startEventSub,
  stopEventSub,
  getRotationStatus,
  toggleRotation,
  setRotationSettings,
  getLogs,
  type Status,
  type Category,
  type RotationStatus,
  type DmRecipient,
} from "@/lib/api";
import {
  Loader2,
  LogOut,
  RefreshCw,
  Check,
  X,
  Plus,
  Shuffle,
  Send,
  Trash2,
  Undo2,
} from "lucide-react";

export default function Dashboard() {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(true);
  const [statuses, setStatuses] = useState<Status[]>([]);
  const [approvedStatuses, setApprovedStatuses] = useState<Status[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [eventSubRunning, setEventSubRunning] = useState(false);
  const [rotation, setRotation] = useState<RotationStatus | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [dmRecipients, setDmRecipients] = useState<DmRecipient[]>([]);

  // Form states
  const [newStatus, setNewStatus] = useState("");
  const [newStatusCategory, setNewStatusCategory] = useState("");
  const [newCategory, setNewCategory] = useState("");
  const [customStatus, setCustomStatus] = useState("");
  const [dmUserId, setDmUserId] = useState("");
  const [dmMessage, setDmMessage] = useState("");
  const [rotationMin, setRotationMin] = useState(25);
  const [rotationMax, setRotationMax] = useState(45);

  // Delete confirmation dialog
  const [deleteDialog, setDeleteDialog] = useState<{
    open: boolean;
    type: "status" | "category";
    id?: number;
    name?: string;
    label?: string;
  }>({ open: false, type: "status" });

  const fetchData = useCallback(async () => {
    try {
      const [statusesData, categoriesData, eventSubData, rotationData, logsData, dmRecipientsData] =
        await Promise.all([
          getStatuses(),
          getCategories(),
          getEventSubStatus(),
          getRotationStatus(),
          getLogs(30),
          getDmRecipients(),
        ]);

      setStatuses(statusesData);
      setApprovedStatuses(statusesData.filter(s => s.approved_by_user_id !== null));
      setCategories(categoriesData);
      setEventSubRunning(eventSubData.running);
      setRotation(rotationData);
      setRotationMin(rotationData.interval_min);
      setRotationMax(rotationData.interval_max);
      setLogs(logsData.logs);
      setDmRecipients(dmRecipientsData);
    } catch (error) {
      console.error("Error fetching data:", error);
    }
  }, []);

  useEffect(() => {
    const checkAuthAndFetch = async () => {
      try {
        const authStatus = await checkAuth();
        if (!authStatus.authenticated) {
          router.push("/login");
          return;
        }
        await fetchData();
      } catch {
        router.push("/login");
      } finally {
        setIsLoading(false);
      }
    };

    checkAuthAndFetch();

    // Auto-refresh logs every 10 seconds
    const interval = setInterval(async () => {
      try {
        const logsData = await getLogs(30);
        setLogs(logsData.logs);
      } catch {
        // Ignore errors for log refresh
      }
    }, 10000);

    return () => clearInterval(interval);
  }, [router, fetchData]);

  const handleLogout = async () => {
    try {
      await logout();
      router.push("/login");
    } catch {
      router.push("/login");
    }
  };

  const handleAddStatus = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newStatus || !newStatusCategory) return;

    try {
      await addStatus(newStatus, newStatusCategory);
      toast.success("Status dodany");
      setNewStatus("");
      fetchData();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Błąd");
    }
  };

  const openDeleteStatusDialog = (id: number, statusText: string) => {
    setDeleteDialog({ open: true, type: "status", id, label: statusText });
  };

  const handleDeleteStatus = async (id: number) => {
    try {
      await deleteStatus(id);
      toast.success("Status usunięty");
      fetchData();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Błąd");
    }
  };

  const handleApproveStatus = async (id: number) => {
    try {
      await approveStatus(id);
      toast.success("Status zatwierdzony");
      fetchData();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Błąd");
    }
  };

  const handleRevokeStatus = async (id: number) => {
    try {
      await revokeStatus(id);
      toast.success("Zatwierdzenie cofnięte");
      fetchData();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Błąd");
    }
  };

  const handleAddCategory = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCategory) return;

    try {
      await addCategory(newCategory);
      toast.success("Kategoria dodana");
      setNewCategory("");
      fetchData();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Błąd");
    }
  };

  const openDeleteCategoryDialog = (name: string) => {
    setDeleteDialog({ open: true, type: "category", name, label: name });
  };

  const handleDeleteCategory = async (name: string) => {
    try {
      await deleteCategory(name);
      toast.success("Kategoria usunięta");
      fetchData();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Błąd");
    }
  };

  const confirmDelete = async () => {
    if (deleteDialog.type === "status" && deleteDialog.id) {
      await handleDeleteStatus(deleteDialog.id);
    } else if (deleteDialog.type === "category" && deleteDialog.name) {
      await handleDeleteCategory(deleteDialog.name);
    }
    setDeleteDialog({ open: false, type: "status" });
  };

  const handleChangeStatus = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!customStatus) return;

    try {
      await changeStatus(customStatus);
      toast.success("Status zmieniony");
      setCustomStatus("");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Błąd");
    }
  };

  const handleRandomStatus = async () => {
    try {
      await changeStatus(undefined, true);
      toast.success("Losowy status ustawiony");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Błąd");
    }
  };

  const handleSendDm = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!dmUserId || !dmMessage) return;

    try {
      await sendDm(dmUserId, dmMessage);
      toast.success("Wiadomość wysłana");
      setDmUserId("");
      setDmMessage("");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Błąd");
    }
  };

  const handleToggleEventSub = async () => {
    try {
      if (eventSubRunning) {
        await stopEventSub();
        toast.success("EventSub zatrzymany");
      } else {
        await startEventSub();
        toast.success("EventSub uruchomiony");
      }
      fetchData();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Błąd");
    }
  };

  const handleToggleRotation = async () => {
    try {
      await toggleRotation();
      toast.success("Rotacja przełączona");
      fetchData();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Błąd");
    }
  };

  const handleSaveRotationSettings = async () => {
    try {
      await setRotationSettings(rotationMin, rotationMax);
      toast.success("Ustawienia zapisane");
      fetchData();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Błąd");
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container mx-auto flex h-14 items-center justify-between px-4">
          <h1 className="text-lg sm:text-xl font-semibold">Bot Panel</h1>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <Button variant="ghost" size="icon" onClick={handleLogout}>
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="container mx-auto px-4 py-6 space-y-6 max-w-6xl">
        {/* Status Cards */}
        <div className="grid gap-4 md:grid-cols-2">
          {/* EventSub Status */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">EventSub (Twitch)</CardTitle>
            </CardHeader>
            <CardContent className="flex items-center justify-between">
              <Badge variant={eventSubRunning ? "default" : "secondary"}>
                {eventSubRunning ? "Działa" : "Zatrzymany"}
              </Badge>
              <Button size="sm" onClick={handleToggleEventSub}>
                {eventSubRunning ? "Zatrzymaj" : "Uruchom"}
              </Button>
            </CardContent>
          </Card>

          {/* Rotation Status */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Rotacja statusów</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <Badge variant={rotation?.enabled ? "default" : "secondary"}>
                  {rotation?.enabled ? "Włączona" : "Wyłączona"}
                </Badge>
                <Button size="sm" onClick={handleToggleRotation}>
                  {rotation?.enabled ? "Zatrzymaj" : "Uruchom"}
                </Button>
              </div>
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <Input
                  type="number"
                  value={rotationMin}
                  onChange={(e) => setRotationMin(Number(e.target.value))}
                  className="w-20 h-10 text-base"
                  min={1}
                  max={120}
                />
                <span>-</span>
                <Input
                  type="number"
                  value={rotationMax}
                  onChange={(e) => setRotationMax(Number(e.target.value))}
                  className="w-20 h-10 text-base"
                  min={1}
                  max={240}
                />
                <span>min</span>
                <Button size="sm" variant="outline" onClick={handleSaveRotationSettings} className="h-10">
                  Zapisz
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                Zatwierdzonych: {rotation?.approved_count ?? 0}
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Discord Actions */}
        <Card>
          <CardHeader>
            <CardTitle>Akcje Discord</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Zmień status</Label>
              <form onSubmit={handleChangeStatus} className="flex flex-col sm:flex-row gap-2">
                <Input
                  placeholder="Wpisz lub wybierz status..."
                  value={customStatus}
                  onChange={(e) => setCustomStatus(e.target.value)}
                  list="approved-statuses-list"
                  className="flex-1 h-10 text-base"
                />
                <datalist id="approved-statuses-list">
                  {approvedStatuses.map((status) => (
                    <option key={status.id} value={status.status} />
                  ))}
                </datalist>
                <div className="flex gap-2">
                  <Button type="submit" size="icon" className="h-10 w-10">
                    <Check className="h-4 w-4" />
                  </Button>
                  <Button type="button" variant="outline" onClick={handleRandomStatus} className="h-10">
                    <Shuffle className="h-4 w-4 mr-2" />
                    Losowy
                  </Button>
                </div>
              </form>
            </div>

            <div className="space-y-2">
              <Label>Wyślij DM</Label>
              <form onSubmit={handleSendDm} className="flex flex-col sm:flex-row gap-2">
                <Input
                  placeholder="ID użytkownika lub wybierz..."
                  value={dmUserId}
                  onChange={(e) => setDmUserId(e.target.value)}
                  list="dm-recipients-list"
                  className="w-full sm:w-64 h-10 text-base"
                />
                <datalist id="dm-recipients-list">
                  {dmRecipients.map((r) => (
                    <option key={r.user_id} value={r.user_id}>
                      {r.display_name} (@{r.username})
                    </option>
                  ))}
                </datalist>
                <Input
                  placeholder="Treść wiadomości"
                  value={dmMessage}
                  onChange={(e) => setDmMessage(e.target.value)}
                  className="flex-1 h-10 text-base"
                />
                <Button type="submit" className="h-10">
                  <Send className="h-4 w-4 mr-2" />
                  Wyślij
                </Button>
              </form>
            </div>
          </CardContent>
        </Card>

        {/* Categories */}
        <Card>
          <CardHeader>
            <CardTitle>Kategorie</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-2">
              {categories.map((cat) => (
                <Badge key={cat.id} variant="secondary" className="gap-1 pr-1">
                  {cat.label}
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-4 w-4 hover:bg-destructive hover:text-destructive-foreground"
                    onClick={() => openDeleteCategoryDialog(cat.label)}
                  >
                    <X className="h-3 w-3" />
                  </Button>
                </Badge>
              ))}
            </div>
            <form onSubmit={handleAddCategory} className="flex flex-col sm:flex-row gap-2">
              <Input
                placeholder="Nazwa nowej kategorii"
                value={newCategory}
                onChange={(e) => setNewCategory(e.target.value)}
                className="flex-1 h-10 text-base"
              />
              <Button type="submit" className="h-10">
                <Plus className="h-4 w-4 mr-2" />
                Dodaj
              </Button>
            </form>
          </CardContent>
        </Card>

        {/* Statuses */}
        <Card>
          <CardHeader>
            <CardTitle>Statusy</CardTitle>
            <CardDescription>
              <form onSubmit={handleAddStatus} className="flex flex-col sm:flex-row gap-2 mt-2">
                <Select value={newStatusCategory} onValueChange={setNewStatusCategory}>
                  <SelectTrigger className="w-full sm:w-48 h-10">
                    <SelectValue placeholder="Kategoria" />
                  </SelectTrigger>
                  <SelectContent>
                    {categories.map((cat) => (
                      <SelectItem key={cat.id} value={cat.label}>
                        {cat.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Input
                  placeholder="Treść statusu"
                  value={newStatus}
                  onChange={(e) => setNewStatus(e.target.value)}
                  className="flex-1 h-10 text-base"
                />
                <Button type="submit" className="h-10">
                  <Plus className="h-4 w-4 mr-2" />
                  Dodaj
                </Button>
              </form>
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="rounded-md border overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="hidden sm:table-cell">ID</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="hidden md:table-cell">Kategoria</TableHead>
                    <TableHead className="hidden lg:table-cell">Autor</TableHead>
                    <TableHead>Stan</TableHead>
                    <TableHead className="text-right">Akcje</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {statuses.map((status) => (
                    <TableRow key={status.id}>
                      <TableCell className="hidden sm:table-cell font-mono text-xs">
                        {status.id}
                      </TableCell>
                      <TableCell className="max-w-[200px] truncate">
                        {status.status}
                      </TableCell>
                      <TableCell className="hidden md:table-cell">
                        {status.category}
                      </TableCell>
                      <TableCell className="hidden lg:table-cell">
                        {status.person_name}
                      </TableCell>
                      <TableCell>
                        {status.approved_by_user_id ? (
                          <Badge variant="default">Tak</Badge>
                        ) : (
                          <Badge variant="outline">Nie</Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1">
                          {!status.approved_by_user_id ? (
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-10 w-10 text-green-500 hover:text-green-600"
                              onClick={() => handleApproveStatus(status.id)}
                              title="Zatwierdź"
                            >
                              <Check className="h-5 w-5" />
                            </Button>
                          ) : (
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-10 w-10 text-yellow-500 hover:text-yellow-600"
                              onClick={() => handleRevokeStatus(status.id)}
                              title="Cofnij zatwierdzenie"
                            >
                              <Undo2 className="h-5 w-5" />
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-10 w-10 text-destructive hover:text-destructive"
                            onClick={() => openDeleteStatusDialog(status.id, status.status)}
                            title="Usuń"
                          >
                            <Trash2 className="h-5 w-5" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>

        {/* Logs */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle>Logi</CardTitle>
            <Button
              variant="outline"
              size="sm"
              onClick={async () => {
                const data = await getLogs(30);
                setLogs(data.logs);
                toast.success("Logi odświeżone");
              }}
            >
              <RefreshCw className="h-4 w-4 mr-2" />
              Odśwież
            </Button>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-[200px] rounded-md border bg-muted/50 p-4">
              <pre className="text-xs font-mono whitespace-pre-wrap text-green-500">
                {logs.join("")}
              </pre>
            </ScrollArea>
          </CardContent>
        </Card>
      </main>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialog.open} onOpenChange={(open) => setDeleteDialog({ ...deleteDialog, open })}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Potwierdzenie usunięcia</DialogTitle>
            <DialogDescription>
              Czy na pewno chcesz usunąć {deleteDialog.type === "status" ? "status" : "kategorię"}:{" "}
              <span className="font-semibold text-foreground">&quot;{deleteDialog.label}&quot;</span>?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialog({ open: false, type: "status" })}>
              Anuluj
            </Button>
            <Button variant="destructive" onClick={confirmDelete}>
              Usuń
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
