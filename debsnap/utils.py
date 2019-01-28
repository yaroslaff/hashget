
def kmgt(sz, frac=1):
    t={
        'K': pow(1024,1),
        'M': pow(1024,2),
        'G': pow(1024,3),
        'T': pow(1024,4),
        '': 1}

    for k in sorted(t,key=t.__getitem__,reverse=True):
        fmul = pow(10,frac)

        if sz>=t[k]:
            #n = int((float(sz)*fmul / t[k]))
            n = sz/float(t[k])
            #n = n/float(fmul)

            tpl = "{:."+str(frac)+"f}{}"

            return tpl.format(n,k)

