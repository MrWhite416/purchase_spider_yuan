function l(t, e) {
            return t.toString().toUpperCase() > e.toString().toUpperCase()
                ?
                1
                :
                t.toString().toUpperCase() == e.toString().toUpperCase()
                    ?
                    0
                    :
                    -1
        }