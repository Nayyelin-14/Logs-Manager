import { useCallback, useEffect, useState } from "react";
import { useInfiniteQuery, QueryClient } from "@tanstack/react-query";

import {
  Search,
  ChevronDown,
  LoaderCircle,
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
  invalidateRuleQueries,
  RulesInfiniteQueryWithFilters,
} from "../../api/query";
import { useSecurityEventFilterStore } from "../../store/filterStore";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../../components/ui/dialog";

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
import { AlertRuleForm } from "../Forms/RuleForm";

interface TenantType {
  tenant: string;
}

const AllRulesTable = ({ tenant }: TenantType) => {
  const [, setSearchParams] = useState(new URLSearchParams());

  const [isOpen, setIsOpen] = useState(false);
  const [, setShowFilters] = useState({
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
    isFetchingNextPage,
    fetchNextPage,
    hasNextPage,
    isFetching,
    refetch,
  } = useInfiniteQuery(
    RulesInfiniteQueryWithFilters({ ...filterValues, tenant })
  );

  const allRules = data?.pages.flatMap((page) => page.rules) ?? [];

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
        queryKey: ["rules", "infinite", updatedFilters],
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
    queryClient.removeQueries({
      queryKey: ["rules", "infinite", filterValues],
    });
  }, [filterValues, removeFilters]);

  useEffect(() => {
    const handler = setTimeout(() => {
      handleFilterChange("search", searchTerm);
    }, 400); // 400ms debounce

    return () => clearTimeout(handler); // cleanup previous timer
  }, [handleFilterChange, searchTerm]);

  const { mutate: deleteRule, isPending: ruleDeleting } = useAppMutation({
    endpoint: (ruleId: string) => `/delete-rule/${ruleId}`,
    method: "delete",
    invalidateFn: async () => {
      await invalidateRuleQueries();
      await invalidateAllDataCount(tenant);
    },
  });

  const handleConfirm = (ruleId: string) => {
    deleteRule(ruleId);
  };

  return (
    <div className="border border-gray-100 p-4 rounded-md shadow-md" id="rules">
      <div className="flex items-center justify-between py-4">
        <h1 className="text-2xl font-extrabold">All alert rules</h1>
        <Dialog open={isOpen} onOpenChange={setIsOpen}>
          <DialogTrigger asChild>
            <button className="bg-blue-600 hover:bg-blue-700 text-white cursor-pointer p-2 sm:px-4 sm:py-2 rounded-lg inline-flex items-center gap-2 text-xs md:text-base">
              <Plus size={16} type="button" />
              New Alert
            </button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create New Alert Rule</DialogTitle>
            </DialogHeader>
            <div className="mt-4">
              <AlertRuleForm setOpen={setIsOpen} tenant={tenant} />
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <div className="flex flex-col md:flex-row md:items-center gap-4 mb-4">
        <div className="relative  md:w-[500px] w-[300px] ">
          <Search
            className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400"
            size={20}
          />
          <input
            type="text"
            placeholder="Search by name or description..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        {/* Date Filter */}
        <div className="flex items-center gap-4">
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
              <TableHead>Name</TableHead>
              <TableHead>Description</TableHead>

              <TableHead>Tenant</TableHead>
              <TableHead>WindowSecond</TableHead>
              <TableHead>Threshold</TableHead>
              <TableHead>Timestamp</TableHead>
              <TableHead>Delete</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {allRules.length > 0 ? (
              allRules.map((rule, index) => (
                <TableRow key={index}>
                  <TableCell>{rule.name}</TableCell>
                  <TableCell>{rule.description}</TableCell>
                  <TableCell>{rule.tenant}</TableCell>
                  <TableCell>
                    {rule.conditions[0]?.windowSeconds ?? "-"}
                  </TableCell>
                  <TableCell>{rule.conditions[0]?.threshold ?? "-"}</TableCell>

                  <TableCell>
                    {rule.createdAt &&
                      new Date(rule.createdAt).toISOString().split("T")[0]}
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
                            disabled={ruleDeleting}
                            onClick={() => {}}
                          >
                            Cancel
                          </AlertDialogCancel>
                          <AlertDialogAction
                            disabled={ruleDeleting}
                            onClick={() => handleConfirm(rule.id)}
                          >
                            {ruleDeleting ? "Deleting..." : "Confirm"}
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
                    No rules found.
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
          Showing {allRules.length} events
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

export default AllRulesTable;
