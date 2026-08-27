import { useEffect, useState } from "react";
import {
  collection,
  query,
  orderBy,
  limit,
  onSnapshot,
} from "firebase/firestore";
import {
  Badge,
  Box,
  Link,
  Table,
  TableContainer,
  Tbody,
  Td,
  Text,
  Th,
  Thead,
  Tr,
} from "@chakra-ui/react";
import { db } from "./firebase.js";

const STATUS_STYLES = {
  queued: { label: "Queued", colorScheme: "gray" },
  starting: { label: "Starting", colorScheme: "orange" },
  running: { label: "Running", colorScheme: "blue" },
  done: { label: "Done", colorScheme: "green" },
  no_changes: { label: "No changes", colorScheme: "yellow" },
  failed: { label: "Failed", colorScheme: "red" },
};

function StatusBadge({ status }) {
  const style = STATUS_STYLES[status] ?? {
    label: status ?? "Unknown",
    colorScheme: "gray",
  };
  return (
    <Badge colorScheme={style.colorScheme} variant="subtle" borderRadius="md">
      {style.label}
    </Badge>
  );
}

function formatTime(ts) {
  if (!ts) return "—";
  const date = ts.toDate ? ts.toDate() : new Date(ts);
  return date.toLocaleString();
}

export default function App() {
  const [tasks, setTasks] = useState(null); // null = loading, [] = loaded/empty
  const [error, setError] = useState(null);

  useEffect(() => {
    const q = query(
      collection(db, "tasks"),
      orderBy("created_at", "desc"),
      limit(50),
    );
    const unsubscribe = onSnapshot(
      q,
      (snapshot) => {
        setTasks(snapshot.docs.map((d) => ({ id: d.id, ...d.data() })));
        setError(null);
      },
      (err) => setError(err.message),
    );
    return unsubscribe;
  }, []);

  let body;
  if (error) {
    body = (
      <Tr>
        <Td colSpan={5} textAlign="center" color="red.500" py={12}>
          Couldn't load tasks: {error}
        </Td>
      </Tr>
    );
  } else if (tasks === null) {
    body = (
      <Tr>
        <Td colSpan={5} textAlign="center" color="gray.500" py={12}>
          Loading&hellip;
        </Td>
      </Tr>
    );
  } else if (tasks.length === 0) {
    body = (
      <Tr>
        <Td colSpan={5} textAlign="center" color="gray.500" py={12}>
          No tasks yet. Send a message to get started.
        </Td>
      </Tr>
    );
  } else {
    body = tasks.map((task) => (
      <Tr key={task.id} _hover={{ bg: "gray.50" }}>
        <Td>
          <StatusBadge status={task.status} />
        </Td>
        <Td>
          <Text noOfLines={2}>{task.prompt}</Text>
          {task.error && (
            <Text mt={1} fontSize="sm" color="red.500">
              {task.error}
            </Text>
          )}
        </Td>
        <Td>
          <Text fontFamily="mono" fontSize="sm" color="gray.600">
            {task.repo || "—"}
          </Text>
          {task.from_whatsapp && (
            <Text fontSize="xs" color="gray.500">
              {task.from_whatsapp.replace("whatsapp:", "")}
            </Text>
          )}
        </Td>
        <Td whiteSpace="nowrap">
          <Text fontFamily="mono" fontSize="sm" color="gray.600">
            {formatTime(task.created_at)}
          </Text>
        </Td>
        <Td>
          {task.pr_url ? (
            <Link href={task.pr_url} isExternal color="blue.500" fontSize="sm">
              View PR &rarr;
            </Link>
          ) : (
            <Text color="gray.400">&mdash;</Text>
          )}
        </Td>
      </Tr>
    ));
  }

  return (
    <Box minH="100vh" bg="white">
      <TableContainer>
        <Table variant="simple" size="md">
          <Thead>
            <Tr>
              <Th>Status</Th>
              <Th>Prompt</Th>
              <Th>Repo</Th>
              <Th>Created</Th>
              <Th>PR</Th>
            </Tr>
          </Thead>
          <Tbody>{body}</Tbody>
        </Table>
      </TableContainer>
    </Box>
  );
}
