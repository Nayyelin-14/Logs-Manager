import { useCallback, useEffect, useState } from "react";
import { useInfiniteQuery, QueryClient } from "@tanstack/react-query";

import {
  Search,
  ChevronDown,
  LoaderCircle,
  Filter,
  Trash,
  Calendar,
  Plus,
} from "lucide-react";
import { DayPicker } from "react-day-picker";
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from "../../components/ui/popover";
import { Button } from "../../components/ui/button";
import { cn } from "../../lib/utils";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../../components/ui/table";

import {
  invalidateAllDataCount,
  invalidateDashboardStats,
  invalidateLogQueries,
  LogsInfiniteQueryWithFilters,
} from "../../api/query";
import { useSecurityEventFilterStore } from "../../store/filterStore";
import { getSeverityStyle, severityOptions } from "../../lib/constants";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../../components/ui/dialog";

import { MultiSourceLogForm } from "../Forms/MultiSourceLogForm";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "../../components/ui/alert-dialog";
import { useAppMutation } from "../../hooks/useMutationApi";
import { useUserStore } from "../../store/userStore";

const AllLogsTable = ({
  tenant,
  range,
}: {
  tenant: string;
  range?: string;
}) => {
  const [searchParams, setSearchParams] = useState(new URLSearchParams());
  const user = useUserStore((state) => state.user);
  const [isOpen, setIsOpen] = useState(false);
  const [showFilters, setShowFilters] = useState({
    date: false,
    source: false,
    severity: false,
  });
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<Date | undefined>(undefined);
  const { filterValues, updateFilter, removeFilters } =
    useSecurityEventFilterStore();
  const [searchTerm, setSearchTerm] = useState(filterValues.search || "");

  const activeFiltersCount = Object.values(filterValues).filter(Boolean).length;
  const {
    data,
    status,
    isFetchingNextPage,
    fetchNextPage,
    hasNextPage,
    isFetching,
    refetch,
  } = useInfiniteQuery(
    LogsInfiniteQueryWithFilters({ ...filterValues, tenant })
  );

  const allEvents = data?.pages.flatMap((page) => page.logs) ?? [];

  const handleFilterChange = useCallback(
    (filterType: keyof typeof filterValues, value: string) => {
      const queryClient = new QueryClient();
      // Build updated filters object manually
      const updatedFilters = { ...filterValues, [filterType]: value };

      // Update the store
      updateFilter(filterType, value);

      // Close popover if date
      if (filterType === "date") setOpen(false);
      setShowFilters((prev) => ({ ...prev, [filterType]: false }));

      // Update URLSearchParams
      const newParams = new URLSearchParams();
      Object.entries(updatedFilters).forEach(([k, v]) => {
        if (v !== null && v !== undefined && v !== "") {
          newParams.set(k, String(v));
        }
      });
      setSearchParams(newParams);

      // Refetch query
      queryClient.invalidateQueries({
        queryKey: ["logs", "infinite", updatedFilters],
      });
    },
    [filterValues, updateFilter]
  );

  const clearFilters = useCallback(() => {
    const queryClient = new QueryClient();
    removeFilters();
    setShowFilters({ date: false, source: false, severity: false });
    setSearchParams(new URLSearchParams());
    setSearchTerm("");
    queryClient.removeQueries({ queryKey: ["logs", "infinite", filterValues] });
  }, [filterValues, removeFilters]);

  useEffect(() => {
    const handler = setTimeout(() => {
      handleFilterChange("search", searchTerm);
    }, 400); // 400ms debounce

    return () => clearTimeout(handler); // cleanup previous timer
  }, [handleFilterChange, searchTerm]);

  const { mutate: deleteLog, isPending: logDeleting } = useAppMutation({
    endpoint: (logId: string) => `/delete-log/${logId}`,
    method: "delete",
    invalidateFn: async () => {
      await invalidateLogQueries();
      await invalidateAllDataCount(tenant);
      await invalidateDashboardStats(tenant, range, user?.id.toString());
    },
    successMessage: "User has been deleted successfully.",
    errorMessage: "Failed to delete user.",
  });

  const handleConfirm = (logId: string) => {
    deleteLog(logId);
  };
  // console.log(allEvents);
  return (
    <div className="border border-gray-100 p-4 rounded-md shadow-md">
      <div className="flex items-center justify-between py-4">
        <h1 className="text-2xl font-extrabold">Security Events</h1>
        <Dialog open={isOpen} onOpenChange={setIsOpen}>
          <DialogTrigger asChild>
            <button className="bg-blue-600 hover:bg-blue-700 text-white cursor-pointer p-2 sm:px-4 sm:py-2 rounded-lg inline-flex items-center gap-2 text-xs md:text-base">
              <Plus size={16} type="button" />
              Create New Log
            </button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create New Log</DialogTitle>
            </DialogHeader>
            <div className="mt-4">
              <MultiSourceLogForm
                setIsOpen={setIsOpen}
                tenant={tenant}
                range={range}
              />
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <div className="relative  md:w-[500px] w-[300px] mb-4">
        <Search
          className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400"
          size={20}
        />
        <input
          type="text"
          placeholder="Search by user, IP, or source..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>

      <div className="flex md:items-center gap-4 md:flex-row flex-col">
        {/* Date Filter */}
        <div className="flex flex-col  ">
          <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger asChild>
              <Button
                variant="outline"
                className={cn(
                  filterValues.date && "bg-yellow-200",
                  "w-42 justify-between font-semibold cursor-pointer h-10 border border-gray-300 "
                )}
              >
                <Calendar />
                {filterValues.date
                  ? new Date(filterValues.date).toISOString().split("T")[0]
                  : "Select date"}
                <ChevronDown className="ml-2 h-4 w-4 opacity-50" />
              </Button>
            </PopoverTrigger>
            <PopoverContent
              className="w-auto overflow-hidden p-0"
              align="start"
            >
              <DayPicker
                animate
                mode="single"
                selected={selected}
                onSelect={(d) => {
                  if (d) {
                    setSelected(d);
                    handleFilterChange("date", d.toISOString().split("T")[0]);
                    setOpen(false);
                  }
                }}
              />
            </PopoverContent>
          </Popover>
        </div>

        <div className="relative flex items-center">
          <button
            onClick={() =>
              setShowFilters((prev) => ({ ...prev, severity: !prev.severity }))
            }
            className={cn(
              "flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 cursor-pointer",
              filterValues.severity && "bg-blue-200"
            )}
          >
            <Filter size={16} />
            Severity: {filterValues.severity || "All"}
            <ChevronDown size={16} />
          </button>
          {showFilters.severity && (
            <div className="absolute top-12 left-0 bg-white border border-gray-300 rounded-lg shadow-lg z-10 min-w-32">
              {severityOptions.map((option) => (
                <button
                  key={option.value}
                  onClick={() => handleFilterChange("severity", option.value)}
                  className="w-full text-left px-4 py-2 hover:bg-gray-50 first:rounded-t-lg last:rounded-b-lg"
                >
                  {option.label}
                </button>
              ))}
            </div>
          )}
          {activeFiltersCount > 0 && (
            <button
              onClick={clearFilters}
              className="text-red-600 cursor-pointer hover:text-red-700 px-3 py-2 text-sm font-medium"
            >
              Clear Filters ({activeFiltersCount})
            </button>
          )}
        </div>
      </div>

      {isFetching && !isFetchingNextPage ? (
        <div className="flex items-center justify-center h-[300px]">
          <LoaderCircle className="animate-spin text-blue-600" size={40} />
        </div>
      ) : (
        <Table>
          <TableCaption>Recent security events</TableCaption>
          <TableHeader>
            <TableRow>
              <TableHead>Username</TableHead>
              <TableHead>Source IP</TableHead>
              <TableHead>Source</TableHead>
              <TableHead>Tenant</TableHead>
              <TableHead>Event Type</TableHead>
              <TableHead>Severity</TableHead>
              <TableHead>Timestamp</TableHead>
              <TableHead>Delete</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {allEvents.length > 0 ? (
              allEvents.map((event, index) => (
                <TableRow key={index}>
                  <TableCell>{event.user}</TableCell>
                  <TableCell>{event.srcIp}</TableCell>
                  <TableCell>{event.source}</TableCell>
                  <TableCell>{event.tenant}</TableCell>
                  <TableCell>{event.eventType}</TableCell>
                  <TableCell>
                    <span
                      className={cn(
                        "inline-flex px-2 py-1 text-sm font-semibold rounded-full",
                        getSeverityStyle(event.severityLevel).bg,
                        getSeverityStyle(event.severityLevel).text
                      )}
                    >
                      {getSeverityStyle(event.severityLevel).label}
                    </span>
                  </TableCell>
                  <TableCell>
                    {event.timestamp &&
                      new Date(event.timestamp).toISOString().split("T")[0]}
                  </TableCell>
                  <TableCell>
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <button
                          className="inline-flex items-center justify-center rounded-md bg-red-500 text-white hover:bg-red-600 
               focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400 
               transition-colors p-2"
                        >
                          <Trash className="h-5 w-5" />
                        </button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>
                            Are you absolutely sure?
                          </AlertDialogTitle>
                          <AlertDialogDescription>
                            This action cannot be undone. This will permanently
                            delete your account and remove your data from our
                            servers.
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel
                            disabled={logDeleting}
                            onClick={() => {}}
                          >
                            Cancel
                          </AlertDialogCancel>
                          <AlertDialogAction
                            disabled={logDeleting}
                            onClick={() => handleConfirm(event.id)}
                          >
                            {logDeleting ? "Deleting..." : "Confirm"}
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </TableCell>
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={8} className="p-0 h-[300px]">
                  <div className="flex items-center justify-center py-12 text-gray-500">
                    No events found.
                    <button
                      className="text-blue-600 hover:underline focus:outline-none cursor-pointer"
                      onClick={() => refetch()}
                    >
                      Try again
                    </button>
                  </div>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      )}

      {/* Pagination */}
      <div className="bg-gray-50 px-6 py-3 flex items-center justify-between border-t">
        <div className="text-sm text-gray-700">
          Showing {allEvents.length} events
        </div>
        <Button
          onClick={() => fetchNextPage()}
          disabled={!hasNextPage || isFetchingNextPage}
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm cursor-pointer"
          variant={!hasNextPage ? "ghost" : "secondary"}
        >
          {isFetchingNextPage
            ? "Loading more"
            : hasNextPage
            ? "Load more"
            : "Nothing more"}
        </Button>
      </div>
    </div>
  );
};

export default AllLogsTable;
