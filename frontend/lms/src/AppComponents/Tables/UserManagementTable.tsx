import { useCallback, useEffect, useState } from "react";
import { Button } from "../../components/ui/button";
import "react-day-picker/style.css";
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
  Search,
  Plus,
  ChevronDown,
  Users,
  Filter,
  Calendar,
  Trash,
  LoaderCircle,
  User,
} from "lucide-react";
import type { Role, Status } from "../../types/types";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "../../components/ui/popover";
import { DayPicker } from "react-day-picker";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../../components/ui/dialog";
import CreateForm from "../Forms/CreateForm";
import { cn } from "../../lib/utils";
import { useSearchParams } from "react-router";
import { useUserFilterStore } from "../../store/filterStore";
import { useInfiniteQuery } from "@tanstack/react-query";
import {
  invalidateAllDataCount,
  invalidateUserQueries,
  queryClient,
  UsersInfiniteQueryWithFilters,
} from "../../api/query";
import {
  getRoleBadge,
  getStatusBadge,
  roleOptions,
  statusOptions,
} from "../../lib/constants";
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
interface TenantType {
  tenant: string;
}

const UserManagementTable = ({ tenant }: TenantType) => {
  const [loading] = useState(false);
  const [searchParams, setSearchParams] = useSearchParams();

  const [open, setOpen] = useState(false);

  const [isOpen, setIsOpen] = useState(false);
  const { filterValues, updateFilter, removeFilters } = useUserFilterStore();
  const [showFilters, setShowFilters] = useState({
    role: false,
    status: false,
    date: false,
  });
  const activeFiltersCount = Object.values(filterValues).filter(Boolean).length;

  const [selected, setSelected] = useState<Date | undefined>(
    filterValues.date ? new Date(filterValues.date) : undefined
  );
  const [searchTerm, setSearchTerm] = useState(filterValues.search || "");
  const {
    isFetching,
    data,
    status,
    error,
    isFetchingNextPage,
    fetchNextPage,
    hasNextPage,
  } = useInfiniteQuery(
    UsersInfiniteQueryWithFilters({ ...filterValues, tenant })
  );

  const handleFilterChange = useCallback(
    (filterType: keyof typeof filterValues, value: string) => {
      const newFilters = { ...filterValues, [filterType]: value };

      updateFilter(filterType, value);

      if (filterType === "date") setOpen(false);

      setShowFilters((prev) => ({ ...prev, [filterType]: false }));

      const newParams = new URLSearchParams();
      Object.entries(newFilters).forEach(([k, v]) => {
        if (v) newParams.set(k, v);
      });
      setSearchParams(newParams);

      queryClient.cancelQueries({
        queryKey: ["users", "infinite", newFilters],
      });
    },
    [filterValues, setSearchParams, updateFilter]
  );

  const clearFilters = () => {
    removeFilters(); // Zustand store
    setShowFilters({ role: false, status: false, date: false }); // UI
    setSearchParams(new URLSearchParams()); // Reset URL
    setSearchTerm("");
    queryClient.removeQueries({
      queryKey: ["users", "infinite", filterValues],
    });
  };

  const allUsers = data?.pages.flatMap((page) => page.usersList) ?? [];
  useEffect(() => {
    const handler = setTimeout(() => {
      handleFilterChange("search", searchTerm);
    }, 400); // 400ms debounce

    return () => clearTimeout(handler);
  }, [searchTerm]);

  const { mutate: deleteUser, isPending: userDeleting } = useAppMutation({
    endpoint: (userId: number) => `/delete-user/${userId}`,
    method: "delete",
    invalidateFn: async () => {
      await invalidateUserQueries();
      await invalidateAllDataCount(tenant);
    },

    successMessage: "User has been deleted successfully.",
    errorMessage: "Failed to delete user.",
  });

  const handleConfirm = (userId: number) => {
    deleteUser(userId);
  };
  return status === "error" ? (
    <p className="flex items-center justify-center h-screen text-2xl text-red-600">
      {error.message}
    </p>
  ) : (
    <div className="border border-gray-100 p-4 rounded-md shadow-md ">
      <div className="flex items-center justify-between py-4  ">
        <h1 className="text-2xl font-extrabold">All users list</h1>
        <Dialog open={isOpen} onOpenChange={setIsOpen}>
          <DialogTrigger asChild>
            <button className="bg-blue-600 hover:bg-blue-700 text-white p-2 sm:px-4 sm:py-2 rounded-lg flex items-center gap-2 text-xs md:text-base">
              <Plus size={16} />
              Create New User
            </button>
          </DialogTrigger>

          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create New User</DialogTitle>
            </DialogHeader>
            <div className="mt-4">
              <CreateForm
                formName="Create User"
                setOpen={setIsOpen}
                tenant={tenant}
              />
            </div>
          </DialogContent>
        </Dialog>
      </div>
      <div>
        <div className="relative flex-1 max-w-[500px]">
          <Search
            className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400"
            size={20}
          />
          <input
            type="text"
            placeholder="Search by username or email..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>
        <div className=" flex flex-col md:flex-row md:items-center   gap-4 my-4">
          <div className="relative">
            <button
              onClick={() =>
                setShowFilters((prev) => ({ ...prev, role: !prev.role }))
              }
              className={cn(
                "flex items-center gap-2  p-2 md:px-4 md:py-2 border border-gray-300 rounded-lg hover:bg-gray-50",
                filterValues.role && "bg-green-200"
              )}
            >
              <User size={16} />
              <span className="md:text-base text-sm">
                {" "}
                Role: {filterValues.role || "All"}
              </span>
              <ChevronDown size={16} />
            </button>
            {showFilters.role && (
              <div className="absolute top-12 left-0 bg-white border border-gray-300 rounded-lg shadow-lg z-10 min-w-32">
                {roleOptions.map((option) => (
                  <button
                    key={option.value}
                    onClick={() => handleFilterChange("role", option.value)}
                    className="w-full text-left px-4 py-2 hover:bg-gray-50 first:rounded-t-lg last:rounded-b-lg"
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            )}
          </div>
          <div className="relative">
            <button
              onClick={() =>
                setShowFilters((prev) => ({ ...prev, status: !prev.status }))
              }
              className={cn(
                "flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50",
                filterValues.status && "bg-blue-200"
              )}
            >
              <Filter size={16} />
              <span className="md:text-base text-sm">
                {" "}
                Status: {filterValues.status || "All Status"}
              </span>

              <ChevronDown size={16} />
            </button>
            {showFilters.status && (
              <div className="absolute top-12 left-0 bg-white border border-gray-300 rounded-lg shadow-lg z-10 min-w-32">
                {statusOptions.map((option) => (
                  <button
                    key={option.value}
                    onClick={() => handleFilterChange("status", option.value)}
                    className="w-full text-left px-4 py-2 hover:bg-gray-50 first:rounded-t-lg last:rounded-b-lg"
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            )}
          </div>
          {/* Date Filter */}
          <div className="flex flex-col gap-3">
            <Popover open={open} onOpenChange={setOpen}>
              <PopoverTrigger asChild>
                <Button
                  variant="outline"
                  id="date"
                  className={cn(
                    filterValues.date && "bg-yellow-200",
                    "w-48 justify-between font-normal"
                  )}
                >
                  <Calendar />
                  {filterValues.date
                    ? new Date(filterValues.date).toLocaleDateString()
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
          <TableCaption>A list of all users.</TableCaption>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Tenant</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Created Date</TableHead>
              <TableHead>Action</TableHead>
            </TableRow>
          </TableHeader>

          <TableBody className="text-left">
            {allUsers && allUsers.length > 0 ? (
              allUsers.map((user, index) => (
                <TableRow key={index}>
                  <TableCell>{user.username}</TableCell>
                  <TableCell>{user.email}</TableCell>
                  <TableCell>{user.tenant}</TableCell>
                  <TableCell>
                    <span
                      className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getStatusBadge(
                        user.status as Status
                      )}`}
                    >
                      {user.status}
                    </span>
                  </TableCell>

                  <TableCell>
                    <span
                      className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getRoleBadge(
                        user.role as Role
                      )}`}
                    >
                      {user.role}
                    </span>
                  </TableCell>

                  <TableCell>
                    {user.createAt &&
                      new Date(user.createAt).toISOString().split("T")[0]}
                  </TableCell>
                  <TableCell className="flex items-center gap-3">
                    <Button className="cursor-pointer">Edit</Button>
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
                            disabled={userDeleting}
                            onClick={() => {}}
                          >
                            Cancel
                          </AlertDialogCancel>
                          <AlertDialogAction
                            disabled={userDeleting}
                            onClick={() => handleConfirm(user.id)}
                          >
                            Continue
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </TableCell>
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={10} className="p-0">
                  <div className=" overflow-hidden flex items-center justify-center">
                    {loading ? (
                      <div className="flex items-center justify-center py-12">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                        <span className="ml-3 text-gray-600">
                          Loading users...
                        </span>
                      </div>
                    ) : allUsers.length === 0 ? (
                      <div className="mx-auto text-center  py-12">
                        <Users className="mx-auto h-12 w-12 text-gray-400 mb-4" />
                        <h3 className="text-lg font-medium text-gray-900 mb-2">
                          No users found
                        </h3>
                        <p className="text-gray-500 mb-4">
                          {activeFiltersCount > 0
                            ? "No users match your current filters. Try adjusting your search criteria."
                            : "Get started by creating your first user account."}
                        </p>
                        {activeFiltersCount > 0 ? (
                          <button
                            onClick={clearFilters}
                            className="text-blue-600 hover:text-blue-700 font-medium"
                          >
                            Clear all filters
                          </button>
                        ) : (
                          <Dialog>
                            <DialogTrigger asChild>
                              <button className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg inline-flex items-center gap-2">
                                <Plus size={16} />
                                Create New User
                              </button>
                            </DialogTrigger>
                            <DialogContent>
                              <DialogHeader>
                                <DialogTitle>
                                  Are you absolutely sure?
                                </DialogTitle>
                                <DialogDescription>
                                  This action cannot be undone. This will
                                  permanently delete your account and remove
                                  your data from our servers.
                                </DialogDescription>
                              </DialogHeader>
                            </DialogContent>
                          </Dialog>
                        )}
                      </div>
                    ) : null}
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
          Showing {allUsers.length} users
        </div>
        {/* {hasNextPage && ( */}
        <Button
          onClick={() => fetchNextPage()}
          disabled={!hasNextPage || isFetchingNextPage}
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm cursor-pointer"
          variant={!hasNextPage ? "ghost" : "secondary"}
        >
          {isFetchingNextPage // when data is loading, it shows:
            ? "Loading more"
            : hasNextPage
            ? "Load more" //If there are more pages to load
            : "Nothing more"}
          {/* //no more posts */}
        </Button>
        {/* )} */}
      </div>
    </div>
  );
};

export default UserManagementTable;
