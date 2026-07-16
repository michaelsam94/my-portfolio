---
title: "Go Generics in Practice"
slug: "go-generics-in-practice"
description: "Go 1.18+ generics reduce duplication for containers and algorithms. Type parameters, constraints, and patterns that help without over-abstracting."
datePublished: "2025-05-13"
dateModified: "2025-05-13"
tags: ["Backend", "Go", "Generics", "API"]
keywords: "Go generics, type parameters Go, constraints golang, generic functions Go, comparable constraint"
faq:
  - q: "When should I use Go generics?"
    a: "Use generics for reusable data structures—Set, Queue, Option—and algorithms—Map, Filter, Contains—where type safety beats interface{} or code generation. Skip generics for business logic that appears once; duplication may be clearer than abstraction."
  - q: "What is a type constraint in Go?"
    a: "Constraint limits which types satisfy type parameter—built-in comparable, any, or interface defining method set or union of types. Compiler ensures instantiated types match constraint."
  - q: "Do generics slow down Go programs?"
    a: "Generics are monomorphized at compile time—specialized per type argument with no runtime reflection cost in typical use. Binary size can grow with many instantiations; profile if concerned."
---

Before generics we copy-pasted `StringSet`, `IntSet`, and `UUIDSet`—or abused `map[interface{}]struct{}` and lost compile-time keys. Go generics let us write `Set[T comparable]` once. They are not Java templates; restraint keeps Go readable.

## Basic generic function

```go
func Map[T, U any](slice []T, fn func(T) U) []U {
    out := make([]U, len(slice))
    for i, v := range slice {
        out[i] = fn(v)
    }
    return out
}

ids := Map(users, func(u User) string { return u.ID })
```

Type parameters in brackets; arguments inferred at call site often.

## Type constraints

```go
func Sum[T ~int | ~int64 | ~float64](nums []T) T {
    var total T
    for _, n := range nums {
        total += n
    }
    return total
}
```

Union constraint `~int | ~int64` includes defined types based on those primitives.

Define reusable constraint:

```go
type Number interface {
    ~int | ~int8 | ~int16 | ~int32 | ~int64 |
    ~uint | ~float32 | ~float64
}
```

## comparable and maps

Keys in generic sets need `comparable`:

```go
type Set[T comparable] map[T]struct{}

func NewSet[T comparable]() Set[T] {
    return make(Set[T])
}

func (s Set[T]) Add(v T) { s[v] = struct{}{} }
func (s Set[T]) Contains(v T) bool { _, ok := s[v]; return ok }
```

Slices are not comparable—cannot use `[]byte` as Set key without conversion to string.

## Generic data structures

```go
type Stack[T any] struct {
    items []T
}

func (s *Stack[T]) Push(v T) { s.items = append(s.items, v) }

func (s *Stack[T]) Pop() (T, bool) {
    if len(s.items) == 0 {
        var zero T
        return zero, false
    }
    v := s.items[len(s.items)-1]
    s.items = s.items[:len(s.items)-1]
    return v, true
}
```

## Constrained by interface

When algorithm needs methods:

```go
type Stringer interface {
    String() string
}

func Join[T Stringer](items []T, sep string) string {
    strs := make([]string, len(items))
    for i, item := range items {
        strs[i] = item.String()
    }
    return strings.Join(strs, sep)
}
```

Prefer small interface constraints over large ones—Go idiomatic minimal interfaces.

## Generic types in APIs

HTTP helper returning typed JSON:

```go
func DecodeJSON[T any](r io.Reader) (T, error) {
    var v T
    dec := json.NewDecoder(r)
    dec.DisallowUnknownFields()
    err := dec.Decode(&v)
    return v, err
}

user, err := DecodeJSON[User](r.Body)
```

Clearer than `json.Unmarshal` into `interface{}`.

## slices package (Go 1.21+)

Stdlib generics for common ops:

```go
import "slices"

slices.Contains(ids, target)
slices.SortFunc(users, func(a, b User) int {
    return strings.Compare(a.Name, b.Name)
})
```

Prefer stdlib over custom when available.

## When generics hurt

- Single-use helpers—just write concrete code
- Deeply nested type parameters—readability cliff
- Replacing all interfaces—Go still favors implicit satisfaction
- Premature generic repositories—`Repository[T]` often fights ORM specifics

Rule: duplicate twice, abstract on third with generics if types align.

## Instantiation and testing

Test generic code with concrete types:

```go
func TestSet(t *testing.T) {
    s := NewSet[string]()
    s.Add("a")
    if !s.Contains("a") {
        t.Fatal("expected contains")
    }
}
```

No special test syntax—compile instantiates per type argument.

## Avoid generic global state

`var cache GenericCache[T]` often worse than specific typed cache—generics do not require genericizing every struct.

## Copy with generics

```go
func CloneSlice[T ~[]E, E any](s T) T {
    c := make(T, len(s))
    copy(c, s)
    return c
}
```

Stdlib adds helpers over time—check `slices` and `maps` before custom.

## Benchmark monomorphization cost

Binary size grows with many `Set[int]`, `Set[string]`, `Set[uuid.UUID]` instantiations—acceptable unless embedded constraints.

## Read generics proposals for updates

Go release notes may add new constraints syntax—stay current with `cmp.Ordered` and stdlib generic APIs.


## constraints package

Go 1.21+ `cmp.Ordered` for min/max generics:

```go
import "cmp"

func Min[T cmp.Ordered](a, b T) T {
    if a < b { return a }
    return b
}
```

Prefer stdlib over custom when available.

## API stability

Exported generic functions are public API—changing constraint set is breaking change; treat like any exported func signature.

## Reflection vs generics

Generics replace some reflection for type-safe containers—still use reflection for fmt.Stringer debugging or JSON where generics do not help.

## Teaching team

Internal lunch-and-learn: one hour on generics patterns approved in codebase—prevents every engineer inventing own `Optional[T]` incompatible types.

## slices.Clone in Go 1.21

Prefer \`slices.Clone\` over generic CloneSlice unless pre-1.21 support required—stdlib maintained and optimized.

## Rollout guidance

Generics adoption OKR optional team learning goal not mandate—forced generic abstraction rejected code review unless duplication evidence attached PR description three concrete duplicate implementations linked line numbers.

## Team practices

Shipping Go Generics In Practice in production taught our team that documentation beats hero demos. We wrote runbooks covering failure modes, on-call steps, and rollback triggers before the second release, not after the first outage.

When reviewing PRs touching Go Generics In Practice, we ask for measurable outcomes: latency, crash rate, or support ticket volume—not subjective feels faster. If metrics are unavailable, the PR includes a DevTools trace or load test snippet proving the change.

Onboarding engineers paste a checklist into their first Go Generics In Practice PR description: environment setup verified, tests added or updated, accessibility spot-checked, and release notes drafted for user-visible changes.

We keep a living FAQ in the repo wiki for Go Generics In Practice questions repeated in Slack more than twice. FAQ entries link to source files and Slack threads, reducing tribal knowledge and repeated explanations in code review.

## Resources

- [Go generics tutorial](https://go.dev/doc/tutorial/generics)
- [Type parameters proposal (design doc)](https://go.dev/design/43651-type-parameters)
- [slices package](https://pkg.go.dev/slices)
- [maps package](https://pkg.go.dev/maps)
- [Go 1.18 release notes](https://go.dev/doc/go1.18)
